# A/B Findings: JSON vs Git-Refs Task Backend

**Date:** 2026-07-10
**Scope:** `frh-14-git-refs-wiring-parity` — backend-routed sealing, factory/config wiring, and the parity suite that proves `GitRefsBackend` behaves like the JSON backend.
**Question:** Is the opt-in `git-refs` backend behaviorally equivalent to the default JSON backend, and what does it cost?

**Recommendation, up front:** behavior is equivalent; performance is not. Keep `git-refs` as an **opt-in prototype**. Do **not** promote it to the default until multi-task save granularity is addressed (see Known Gaps).

---

## What Was Built

- `TaskBackend.seal(task_id, history_file)` with a default file-based implementation that mirrors `queue.seal_terminal` (remove from live queue, append the full record to the history JSONL). `JsonBackend` inherits it unchanged.
- `GitRefsBackend.seal(...)` overrides it: drop the task's `refs/aet/tasks/<id>` ref, then append the record to the same shared history JSONL both backends read.
- `aet-state._apply_transition` now routes sealing through the backend (`backend.seal(...)`) instead of calling `queue_lib.seal_terminal(backend.queue_file, ...)`. The file-path assumption is out of `aet-state`.
- `backends/factory.py` maps `task_backend: "git-refs"` to `GitRefsBackend`; `aet-setup/bin/configure-task-backend` offers `git-refs` with a "prototype, opt-in" note.
- `tests/test_git_refs_parity.py` drives the same `aet-state` scenario against both backends and asserts identical observable outcomes.

## Parity Results

The parity suite runs one scenario per backend against an otherwise-identical scratch repository (a real merged-branch fixture so `awaiting_merge -> merged` is legal): seed a `blocker`/`dependent` pair, walk the blocker through `planned -> ready -> in_progress -> (set-stage implemented) -> awaiting_merge -> merged`, and compare the live queue and the settled history.

| Test                                            | Result | What it proves                                                     |
| ----------------------------------------------- | ------ | ------------------------------------------------------------------ |
| `test_transition_chain_parity`                  | pass   | Full recorded-forward chain lands the blocker in `merged` on both. |
| `test_set_stage_parity`                         | pass   | `set-stage` records the same stage + `kind: stage` history entry.  |
| `test_dependent_promotion_parity`               | pass   | Sealing the blocker promotes the dependent to `ready` identically. |
| `test_sealing_parity_settled_history_identical` | pass   | The settled JSONL record is equivalent (timestamps aside).         |

The only tolerated differences are wall-clock fields (`at`, `settled_at`, `merged_at`, `completed_at`), which the suite strips before comparing. After normalization, the snapshots are equal across backends — `aet-state` produces the same states, history entries, and settled record regardless of which backend stores the live queue.

## Timing Comparison

Measured on the development host (macOS), 25 iterations per backend, fresh scratch repo each iteration, timing only the scenario body (seed + 4 transitions + set-stage + merge) and a separate 50-task `save`. The full-scenario figure is dominated by per-transition git subprocess spawning; the 50-task save isolates write granularity.

| Metric (median, ms)       | JSON   | git-refs | Ratio (git-refs / JSON) |
| ------------------------- | ------ | -------- | ----------------------- |
| Full parity scenario      | 27.998 | 1324.812 | ~47x                    |
| Single `save` of 50 tasks | 0.973  | 2057.629 | ~2100x                  |

Variance was tight (scenario min/max 1315/1364 ms for git-refs, 26.7/32.5 ms for JSON; 50-task save 1953/2152 ms for git-refs, 0.89/1.23 ms for JSON), so the medians are representative rather than cold-cache noise.

Interpretation: git-refs is **subprocess-bound and proportional to task count**. Each transition cycle runs several git plumbing commands (`for-each-ref`, `rev-parse`, `cat-file`, `hash-object`, `update-ref`), and a bulk `save` writes one blob + one ref per task, so cost scales linearly with the number of live tasks. JSON pays one atomic file write regardless of task count.

Reproduce:

```bash
python3 /tmp/ab_timing.py   # emits per-backend median/min/max for the scenario and a 50-task save
```

(The harness builds the same merged-branch fixture as the parity suite and times both backends over 25 iterations.)

## Worktree-Visibility Demonstration

Refs live in the repository's shared object database and ref namespace, not in a working tree, so a second worktree of the same repo sees the live tasks written from the first. This is the property that justifies a git-native backend: state follows the repo, not a particular checkout.

Covered by `tests/test_git_refs_backend.py::test_refs_visible_from_second_worktree`, which:

1. Creates a second worktree (`git worktree add -b wt2-branch`) sharing the first worktree's object database.
2. Writes a task from a `GitRefsBackend` pointed at the second worktree's queue path.
3. Reads it back from a `GitRefsBackend` pointed at the primary worktree and asserts the task body is visible.

That test passes on this branch, demonstrating cross-worktree visibility end-to-end through the public backend interface.

## Known Gaps

These are the reasons the backend stays opt-in:

1. **Multi-task save granularity.** A single `save` of N tasks performs N `hash-object` + N `update-ref` subprocesses (the ~2100x gap above). The skip-unchanged optimization avoids re-writing identical blobs, but the first write of every changed task is one subprocess each. **Remediation path:** batch the ref updates through one `git update-ref --stdin` (or a single `mktree`/commit) per `save`, collapsing N subprocesses into one. Not done here — out of scope for frh-14, which only had to prove parity and wire the opt-in.
2. **Per-transition subprocess cost.** Even single-task transitions spawn several plumbing commands (~47x slower end-to-end). Acceptable for a prototype at the current queue sizes; would be noticeable on large queues or tight orchestrator loops.
3. **Local-only by design.** Nothing pushes `refs/aet/*`; the backend is a single-clone store unless the operator explicitly syncs those refs. That is intentional for now, but it means the backend does not yet give multi-host queue sharing.
4. **Queue-module double load.** `queue.py` is loaded twice in-process (as `aet_queue` by `aet-state` and as `queue` by the backends), each with its own lock state. `seal` deliberately does **not** re-acquire the queue lock — `aet-state` already holds it — because a nested independent `flock` file descriptor to the same lock file self-deadlocks under POSIX `flock` semantics. The deadlock was hit during this task and resolved by keeping the lock in `aet-state`; the duplicate module load remains as latent technical debt to consolidate in a later ticket.

## Recommendation

**Keep `git-refs` opt-in.** It is behaviorally correct (parity suite green), survives access from a second worktree, and is safely gated behind `task_backend: "git-refs"` with a prototype warning. It is not yet a default candidate: the save-granularity gap (gap 1) is large enough to regress orchestrator throughput on real queues. Promote only after batching the ref writes (gap 1 remediation) brings the bulk-save ratio down near parity and the recommendation is revisited with fresh timing.

`task_backend: "json"` remains the default everywhere; an unknown or unconfigured value still fails loudly to the JSON path, so there is no migration risk for existing projects.

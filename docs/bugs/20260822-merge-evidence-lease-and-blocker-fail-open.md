# Bug Report: the record claimed things that never happened

## Metadata

- **Reported:** 2026-08-22
- **Severity:** critical
- **Status:** resolved
- **Source:** E40 batch run `run-20260822-015936-psnjfhsl`
- **Governing decisions:** ADR-064 (authored for this fix), ADR-011, ADR-059

## Symptoms

Four defects with one theme: **the queue recorded work that did not happen, or
refused to record work that did.**

1. A task branch with zero commits derived as `merged`. `aet state heal --apply`
   sealed such a task as shipped, with a merge commit it invented.
2. A second `aet run` seized the queue from a live run. The incumbent kept
   working but could no longer record anything, and each refused write was
   reported as a task failure — tasks with passing QA verdicts and four commits
   were recorded `failed`.
3. A task was dispatched in parallel with its own blocker, because a blocker
   that was not yet on the board counted as done.
4. `aet status` reported every worktree as stale when run from inside a worktree.

## Reproduction Steps

All four reproduced before any fix. Scripts in the session scratchpad.

**1 — merge evidence.** In a repo with an origin: create `main`, branch
`empty-task` from it, commit nothing.

```
derive_status({"branch": "empty-task"})  ->  merged   (merge_commit: None)
resolve_merge_commit("empty-task")       ->  ('29e477ac…', 'regular', 'ancestry')
```

That sha is `origin/main`'s tip. End to end against a real git-refs queue,
`heal --apply` per stored state:

| stored | outcome before fix |
|---|---|
| `failed` | refused — `Illegal transition: failed -> merged` |
| `in_progress` | refused — same |
| `awaiting_merge` | **applied** — sealed merged, `merge_commit` fabricated |

**2 — lease.** `acquire_lease(q, "run-A")` then `acquire_lease(q, "run-B")`:
run-B takes ownership; run-A then raises `LeaseHeldError` on every write.

**3 — blockers.** `new_task_from_plan(plan blocked_by=[e40-06], live_tasks=[])`
returned `state='ready', pending_blockers=0`.

**4 — worktree.** With `.worktrees/t1` present and recorded relative to the repo
root: `Path(".worktrees/t1").is_dir()` is `True` from the root, `False` from
inside the worktree.

## Root Cause

**1. Ancestry was used as merge evidence.** An undiverged branch sits at its
base and is trivially an ancestor of it, which is indistinguishable by ancestry
from a branch that was merged. `derive_status`, `resolve_merge_commit`,
`validate_transition`, and the `_apply_transition` repair guard all asked the
same question and got the same wrong answer.

No pure-git test separates the two cases — both leave the tip an ancestor of the
trunk with zero commits ahead. The guard proposed in the original report
(`rev-list --count trunk..branch > 0`) measures **0 for both**, and would have
reclassified every merged task as unmerged. The discriminator has to be recorded
at branch creation, which is what ADR-064 decides.

Existing tests did not catch it because every fixture described a branch that
carried work; none described a branch that did not.

**2. `acquire_lease` never checked before claiming.** It wrote the sidecar
unconditionally. Separately, `_record_stage` returned `False` on any nonzero
exit code, and callers converted that into task failure — so "I cannot write
right now" and "the work failed" were the same value.

**3. `b in live_by_id` treated absence as completion.** ADR-059 already settled
that absence is not a fact; the intake filter had not been updated to use the
tombstones that make "sealed" distinguishable from "not added yet".

**4.** A repo-root-relative path was tested against the process working
directory.

## Fix Summary

**Files modified:** `src/aet/cli/aet_state.py`, `src/aet/queue.py`,
`src/aet/cli/orchestrator.py`, `src/aet/cli/next.py`, `src/aet/cli/ship.py`,
`src/aet/cli/sprint.py`, `src/aet/cli/status.py`, `src/aet/plan_parser.py`,
`src/aet/backends/git_refs_backend.py`, plus `docs/adr/064-*.md`.

- **Merge evidence (ADR-064).** `has_merge_evidence()` is the single rule used by
  all four sites: a recorded `merge_commit` that is an ancestor of the target, or
  a branch that has moved past its `base_commit` and is an ancestor. A
  `merge_commit` that is provably the branch's own base is disqualified.
  `resolve_merge_commit` no longer resolves the ancestry path for an undiverged
  branch. Missing `base_commit` fails closed.
- **`base_commit` recorded at branch creation.** `queue.resolve_base_commit()` +
  `record_task_meta(..., base_commit=)`, with **first write winning** so a task
  re-recorded after committing does not stamp its current tip as its origin. All
  three branch-creation sites now route through `record_task_meta` instead of
  hand-rolling the same write.
- **Lease.** `acquire_lease` calls `check_lease` first and raises rather than
  seizing; both `aet run` entry points refuse at startup with a clear message.
  `LEASE_HELD_EXIT_CODE = 75` gives a refusal its own identity; `_record_stage`
  raises `LeaseRefusedError`, and the task is aborted with its recorded state
  left untouched rather than marked failed.
- **Blockers.** A blocker is satisfied only on positive evidence: terminal on the
  board, or carrying a tombstone. `GitRefsBackend.settled_ids()` reads them.
- **Worktree.** Resolved against the repo root.

**Side effects, deliberate:**

- Task records written before ADR-064 have no `base_commit` and will not
  auto-derive `merged` from branch ancestry. They close via
  `aet state record-merge --merge-commit <sha>`, or through the squash/diff
  resolution paths, which match on content the task actually produced.
- ADR-064's Consequences section originally named `aet ship close` as the escape
  hatch for such records. That was wrong — `close` resolves through the same
  ancestry path the ADR closes — and was found only when four `test_ship_close`
  tests went red. The ADR has been corrected to name the working path,
  `aet state record-merge --merge-commit <sha>`.

## Regression Tests

| File | Tests | Covers |
|---|---|---|
| `tests/state/test_merge_evidence.py` | 16 | the defect, the genuine-merge case the rejected guard would have broken, fail-closed, decision-3 resolution, both transition guards, `base_commit` recording incl. first-write-wins |
| `tests/queue/test_lease_ownership.py` | 8 | seizure refused, incumbent still writes, stale-pid reclaim, force override, refusal ≠ work failure |
| `tests/plan/test_blocker_fail_closed.py` | 6 | absent / tombstoned / terminal / in-progress / mixed blockers |
| `tests/cli/test_status_worktree.py` | 3 | from root, from inside a worktree, genuinely-missing still reported |

Verified as genuine by running each new file against unfixed code in a detached
worktree at `6b6b1f62`: the lease and worktree tests fail there on exactly the
defect cases and pass on the control cases. The blocker tests fail there with a
`TypeError` (the `settled_ids` parameter does not exist on `main`), so that run
proves nothing on its own — the evidence for that defect is the direct
reproduction above.

Existing fixtures were updated, never relaxed: each edit adds a `base_commit` and
its matching `rev-parse` mock so the fixture describes a branch that carries
work. One assertion genuinely moved — `test_regular_merge_reports_ancestry` now
passes the base explicitly — and
`test_regular_merge_without_base_commit_does_not_resolve_by_ancestry` was added
to hold the fail-closed behavior it used to cover.

## Validation

- [x] Reproduction steps no longer trigger the bug (heal now reports
      `No healable discrepancies found` for all three stored states)
- [x] No new failures against a measured baseline
- [x] `aet docs lint` passes

**Pre-existing failures on clean `main` (not introduced here):** 8 — six in
`tests/orchestrator` (`TestRunOneQueueBookkeeping` ×3, `TestRunStageGroup` ×2 —
`_StubPopen` has no `pid` in the liveness monitor — and `test_single_pr_rehearsal`),
plus `test_ship_records_merge_seals_task_without_touching_plan` and
`test_gate_evidence`. The suite cannot currently serve as a clean merge gate.

## Deliberately Not Done

- **Re-deriving state at dispatch.** The original report asks to wire the
  derivation into `pick_next_ready`. ADR-011 decision 1 forbids it — state is
  recorded forward and trusted on read, never re-derived — and decision 6 keeps
  the ready frontier maintained forward. With intake now fail-closed, the field
  has a correct starting value and a correct maintainer. Building this would
  contradict an accepted ADR.
- **Persisting unwritable transitions.** A durable-intent mechanism, well beyond
  this fix. The startup guard removes the cause; this would soften the symptom.
- **SIGTERM triage classification.** Reported as a defect, **not reproducible**:
  all three call sites pass `killed_by_timeout=(exit_code < 0)`, implementing
  ADR-060, so a signal-killed worker classifies as `timeout`. Explaining the
  `environment` the triage agent saw needs that run's telemetry.
- **The `.gitignore` / `docs/plans` item.** Not a bug. `.gitignore:27` ignores
  new plan files deliberately (R-4/R-19), so the worker read it correctly. The
  real conflict is that workers are still prompted to land a `Stage:` footer
  commit for a file the repo intentionally does not track. Needs its own
  decision.

## Lessons Learned

- **Pattern:** a proxy signal mistaken for evidence. Ancestry, absence, and a
  nonzero exit code were each read as proof of something they only correlate
  with. In all three, the fix was to require positive evidence and fail closed.
- **Prevention:** when a check answers a question about *history*, ask whether
  the two states it must distinguish are actually distinguishable at the time of
  the check. If not, the discriminator has to be recorded when it is still known.
- **Prevention:** a fix proposed inside a bug report is a hypothesis. This one's
  was wrong in a way that would have broken every merge, and one measurement
  caught it.
- **Reference:** ADR-064; ADR-011 decisions 1, 4, 6; ADR-059.

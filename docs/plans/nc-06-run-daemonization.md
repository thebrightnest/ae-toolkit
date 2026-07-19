---
id: nc-06-run-daemonization
size: L
blocked_by:
  - pkg-04-cli-extraction
pipeline: standard
status: approved
security_review: required
security_review_reason: New process-spawning/detaching code; must not weaken the existing per-task timeout/stall-watchdog kill semantics.
docs_sync: required
docs_sync_reason: .agents/commands/aet-work.md's manual-backgrounding instructions (Bash(run_in_background=..., disable_timeout=...)) become obsolete and must be replaced with the new default-detached behavior.
---

# Plan: Self-Daemonizing `aet run` / `aet run-one`

## Context

Source: `docs/prds/namespace-consolidation-prd.md`, R-6 + Open Question #3. Verified directly against `aet-work/bin/aet`: today, `_exec()` (used uniformly by every `mode: "exec"`/`"run"`/`"run-one"` subcommand) calls `os.execvp`, which **replaces the calling process image** — this is why `aet run`/`aet run-one` block in the foreground today and why `.agents/commands/aet-work.md` currently instructs the agent to manually background them with `Bash(run_in_background=true, disable_timeout=true, command="aet run", ...)` (lines 11-38). That manual workaround is exactly the "agent-facing friction" the 2026-07-19 retro flagged and this PRD's Overview cites for R-6.

Verified directly against `aet-work/bin/orchestrator`: per-task `--task-timeout` (wall-clock) and `--stall-timeout` (stdout-silence watchdog, via a background thread calling `_terminate_process_group`) are existing, working mechanisms internal to the orchestrator's task-spawning loop, unrelated to how the orchestrator process *itself* is launched. Per the PRD's Technical Notes, daemonization "is a presentation-layer change, not new infrastructure" — this ticket must not touch that internal timeout/watchdog logic, only how the orchestrator process is attached to (or detached from) the invoking shell.

`blocked_by: pkg-04-cli-extraction`, not `pkg-06-cross-skill-extraction`, deliberately: pkg-04 relocates `orchestrator` (and `status`) to their final package homes (`src/aet/cli/orchestrator.py`, `src/aet/cli/status.py`) — where this ticket's substantial new logic (detached spawning, run-id/log handling) belongs, written once. The dispatcher file itself (`aet-work/bin/aet`, where the `mode: "run"/"run-one"` flag-parsing and exec-vs-spawn decision lives) does **not** move to its final package home until pkg-06 (confirmed directly in `pkg-04-cli-extraction.md`'s Context: "the dispatcher file itself stays at `aet-work/bin/aet` until pkg-06") — but that glue is thin enough that pkg-06's later mechanical file-move will carry it along unchanged, with no rework. See Rejected Alternatives.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] N/A — no defect redirect needed

## Task List

1. Choose the daemonization mechanism (Open Question #3, an implementation-time call, not decided by this plan): fork/detach, a daemon-lockfile-plus-follow scheme, or supervising via the existing panel server. Document the choice and rationale directly in the code (module docstring of the modified orchestrator entry point) — M (traces: R-6)
2. Modify the orchestrator's entry point (post-pkg-04: `src/aet/cli/orchestrator.py`) to support a detached run mode: assign a run ID, redirect stdout/stderr to a log keyed by that ID, and leave the existing per-task `--task-timeout`/`--stall-timeout` watchdog logic internally unchanged — L (traces: R-6)
3. Modify the dispatcher's `mode: "run"`/`"run-one"` handling (`aet-work/bin/aet`, pre-pkg-06 location) to spawn the orchestrator detached by default instead of calling the shared `_exec()`/`os.execvp` path: print the run ID and return immediately (exit 0). Do not modify `_exec()` itself — it is shared by every other `exec`-mode subcommand; add a new, separate code path specific to `run`/`run-one` — M (traces: R-6)
4. Add a `--foreground` flag to `run`/`run-one` that preserves today's exact blocking behavior (routes to the existing `_exec()` call, unchanged) — for debugging — S (traces: R-6)
5. Add `aet run --follow <run-id>` to attach to and tail a running or already-completed run's output by ID — M (traces: R-6)
6. Extend `aet status` (post-pkg-04: `src/aet/cli/status.py`) to surface active run ID(s), if any, alongside its existing queue-state output — S (traces: R-6)
7. Rewrite `.agents/commands/aet-work.md`'s `aet run` / `aet run-one` sections (lines 11-38): remove the manual `Bash(run_in_background=..., disable_timeout=...)` instructions and their anti-patterns list; document the new default-detached behavior, `aet run --follow <id>`, `aet status`, and `--foreground` — M (traces: R-6, R-7)
8. Add/update tests in `tests/test_orchestrator_daemonize.py` (run-id generation and uniqueness; detached spawn returns promptly without waiting for orchestrator completion; `--follow` attaches correctly to both an in-progress and an already-completed run; `--foreground` reproduces the pre-change blocking behavior exactly) and `tests/test_aet_run_dispatch.py` (dispatcher routes to detached-spawn by default and to `_exec()` only under `--foreground`; existing task-timeout/stall-watchdog tests still pass unchanged post-relocation) — M (traces: R-6)
9. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

> **⚠️ ATOMIC OVERSIZED — requires explicit user approval.**
> "Start non-blocking" (tasks 1-4) and "check on it later" (tasks 5-6) are two
> halves of one indivisible user-visible behavior — a run that cannot later be
> followed or checked on is not usably non-blocking, and a follow/status
> mechanism has nothing to attach to without the detach mechanism existing
> first. Splitting them would be a horizontal cut across a single feature
> ("run the queue without blocking the session"), not a genuine vertical
> slice, and would leave an interim state where starting a run doesn't yet
> let anyone observe it — worse than one larger reviewable diff.

### Batching Check

- [x] This is not one of several near-identical additions.
- [x] The diff is expected to exceed 5 files or 200 lines (orchestrator, dispatcher, status, docs, multiple test files).
- [x] The work cannot share a branch/PR with other tickets — it has its own dependency edge (`pkg-04-cli-extraction`) and reviewable surface distinct from every other ticket in this PRD.

## Rejected Alternatives

- **`blocked_by: pkg-06-cross-skill-extraction` instead of `pkg-04-cli-extraction`** — rejected on inspection: the bulk of this ticket's new code (detached spawning, run-id/log handling) belongs in `orchestrator.py`, whose final package home is settled by pkg-04, not pkg-06 (pkg-06 doesn't touch `orchestrator.py` again). The smaller dispatcher-side glue does live in a file that moves later (pkg-06), but it's thin enough to ride along unchanged in that later mechanical relocation — not worth blocking substantial new work on a later, unrelated relocation.
- **Modifying `_exec()` directly to add detach-vs-foreground branching** — rejected: `_exec()` is shared by every `exec`-mode subcommand (`ship`, `sprint`, `status`, etc.); changing its behavior risks regressing all of them. A new, `run`/`run-one`-specific code path is the safer boundary.
- **Deciding the daemonization mechanism now, during planning** — rejected: Open Question #3 explicitly defers this to implementation time; prescribing fork/detach vs. lockfile vs. panel-supervisor now would remove a decision that needs the actual codebase in hand to make well.
- **Touching the internal `--task-timeout`/`--stall-timeout` watchdog logic** — rejected: the PRD's Technical Notes explicitly frame daemonization as "a presentation-layer change, not new infrastructure"; the watchdog logic is orthogonal and already correct.

## Files to Modify

- `src/aet/cli/orchestrator.py` (post-pkg-04 location)
- `aet-work/bin/aet` (pre-pkg-06 location; dispatcher `mode: "run"`/`"run-one"` handling)
- `src/aet/cli/status.py` (post-pkg-04 location)
- `.agents/commands/aet-work.md`
- `tests/test_orchestrator_daemonize.py` (new)
- `tests/test_aet_run_dispatch.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-6 covered by tasks 1–8; R-7's docs slice covered by task 7; no unknown R-ids cited
- [ ] Named tests per new file: `tests/test_orchestrator_daemonize.py` — run-id uniqueness, detached-spawn-returns-promptly, `--follow` against in-progress and completed runs, `--foreground` behavioral equivalence to pre-change blocking mode; `tests/test_aet_run_dispatch.py` — dispatcher routes to detached-spawn by default and to `_exec()` only under `--foreground`, `_exec()` itself is untouched (regression check against another `exec`-mode subcommand)
- [ ] Test types: unit tests (run-id generation, flag parsing); integration tests (full detached run against a scratch queue fixture, `--follow` attaching mid-run and post-completion); regression test (existing timeout/stall-watchdog tests unchanged post-relocation)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge. `aet run`/`aet run-one` return to blocking `os.execvp` behavior; `.agents/commands/aet-work.md` reverts to the manual-backgrounding instructions. No queue or task state is affected, since daemonization only changes how the orchestrator process is launched, not what it does once running.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | ---------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

`standard`: new process-spawning/detaching code with a real risk of silently breaking the existing timeout/watchdog guarantees — enough blast radius to warrant the default grouping rather than `minimal`.

---

*Stage: plan-approved*
*Next step: run `aet-work`*

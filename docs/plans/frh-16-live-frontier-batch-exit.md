---
id: frh-16-live-frontier-batch-exit
size: S
blocked_by:
  - frh-11-orchestrator-evidence-gates
  - frh-14-git-refs-wiring-parity
pipeline: standard
status: merged
---

# Plan: Widen the Promotion Frontier; Replace the Batch's Silent Spin with Exit-When-Idle

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G5 adjunct; owner-requested 2026-07-09)
- Companion to frh-15 (intake side). Blocked late because it edits `aet-state` (last touched by frh-14) and `orchestrator` (last touched by frh-11).

Two gaps in live flow:

1. The dependent-promotion frontier in `_apply_transition` (`aet-state:324-336`) only promotes dependents whose state is `blocked`. Tasks curated under the pre-frh-15 behavior sit at `planned`, so their counters decrement but they are never promoted. (`cmd_heal` can already repair stragglers — `planned` → `ready` is legal — but the frontier should not need healing.)
2. When the batch has nothing running and nothing ready but non-terminal tasks remain (e.g., everything `awaiting_merge`), `run_batch` spins at `time.sleep(0.2)` forever with no heartbeat (the `continue` skips it) — the 2026-06-18 "hung after marking all tasks complete" learning; the recorded fix added timeouts but no exit condition.

Owner-confirmed semantics: mid-run pickup is wanted — the spawn loop already re-reads the queue each pass, so a `record-merge` executed while the batch is alive promotes dependents and the loop starts them. Promotion stays gated on `merged` (ancestry-verified on `origin/main`) — never `awaiting_merge` — because dependent worktrees are cut from `origin/main` and must contain the blocker's code. A hold-open-after-drain daemon mode is explicitly out of scope (dark-factory build order; gated on the state layer).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. `aet-state` `_apply_transition` frontier: promote when `pending_blockers` hits 0 and the dependent's state is `blocked` **or** `planned`; history entry `by="release"` records the actual from-state — S
2. `orchestrator` `run_batch` wait condition: keep looping while anything is running **or** a task is `ready`/`in_progress`; when the only remaining non-terminal states are `awaiting_merge`/`blocked`/`planned`/`failed` and nothing is running, exit 0 with a leftover report (`N awaiting merge, M blocked, …`) via the existing summary path — S
3. Tests: frontier promotion of a `planned` dependent on `record-merge`; live pickup (task becomes `ready` mid-batch and is spawned); batch exits with report instead of spinning when all tasks reach `awaiting_merge` — M
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines (tests are the bulk)
- [x] Cannot share a branch with related tasks

## Files to Modify

- `aet-work/bin/aet-state`
- `aet-work/bin/orchestrator`
- `tests/test_aet_state.py`
- `tests/test_orchestrator.py`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] Named tests:
  - `test_frontier_promotes_planned_dependent_on_merge` (in `tests/test_aet_state.py`)
  - `test_batch_spawns_task_promoted_mid_run` (in `tests/test_orchestrator.py`)
  - `test_batch_exits_with_report_when_only_awaiting_merge_remains`
- [ ] Manual: a two-task chain where the blocker is merge-verified while the batch runs results in the dependent starting without operator action
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The frontier reverts to blocked-only promotion; the batch reverts to the previous wait behavior. No data changes.

---

_Stage: merged_
_Next step: run `aet-ship`_

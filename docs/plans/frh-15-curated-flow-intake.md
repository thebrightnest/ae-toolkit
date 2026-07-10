---
id: frh-15-curated-flow-intake
size: M
blocked_by:
  - frh-07-status-retirement-state-bin
pipeline: standard
status: merged
---

# Plan: Curated Flow — add Parks Runnable State, sync Stops Auto-Adding

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G5 adjunct; owner-requested 2026-07-09 after the frh sprint was queued)

Curation and flow are currently inverted. `aet-work add` — the intended curation gate — parks every task at `planned` by overwriting the runnable state that `new_task_from_plan` already computed (`add:116` vs `plan_parser:292`), so even zero-blocker tasks never become `ready` without a manual transition. Meanwhile `bin/sync` auto-adds every valid plan not in queue/history, contradicting its own docstring, `aet-work/SKILL.md` ("does not auto-add every approved plan"), and ADR-013's curation rule. Reverse `blocks` edges are only built by `sync`/`init-queue` (duplicated `build_blocks`), so an `add`-only queue has no edges for the dependent-promotion frontier to walk.

Target semantics: **`add` is the sprint door; once inside, the DAG flows.** `add` parks at `ready` (no blockers) or `blocked` (pending blockers) and rebuilds reverse edges; `sync` reconciles but never adds.

Skill-text rider (mandatory, else this creates a new reality gap): `aet-pipeline-plan` Step 3 and `aet-plan`'s completion protocol both instruct/verify that `sync` adds newly created plans — both must switch to explicit `aet-work add`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. Move `build_blocks` into `aet-work/lib/queue.py`; import it from `sync` (drop the local copy; `init-queue`'s copy is left as-is and noted for the next deletion pass) — S
2. `add`: delete the `task["state"] = "planned"` override so the computed `ready`/`blocked` state stands; call `build_blocks` on the queue after append — S
3. `plan_parser.new_task_from_plan`: record the actual initial state in the intake history entry (today it always logs `None→planned`) — S
4. `sync`: remove the auto-add loop (`new_task_from_plan` call and `added` accounting); sync now only preserves/refreshes existing entries, recomputes edges and drift, and reports — M
5. Skill texts: update `aet-pipeline-plan/SKILL.md` Step 3 and `aet-plan/SKILL.md` queue-handoff/completion wording to explicit `aet-work add` (sync reconciles, never adds) — S
6. Tests: `tests/test_aet_work_add_review.py` and `tests/test_init_queue_sync.py` — M
7. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks (frh-16 continues in aet-state/orchestrator)

## Files to Modify

- `aet-work/lib/queue.py`
- `aet-work/bin/add`
- `aet-work/bin/sync`
- `aet-work/lib/plan_parser.py`
- `aet-pipeline-plan/SKILL.md`
- `aet-plan/SKILL.md`
- `tests/test_aet_work_add_review.py`
- `tests/test_init_queue_sync.py`

## Validation Steps

- [x] `make validate` passes; full suite passes (338 passed)
- [x] Named tests:
  - `test_add_parks_ready_when_unblocked` (in `tests/test_aet_work_add_review.py`)
  - `test_add_parks_blocked_with_pending_blockers_and_builds_edges`
  - `test_intake_history_records_actual_initial_state`
  - `test_sync_never_adds_new_plans` (in `tests/test_init_queue_sync.py`)
  - `test_sync_still_reports_drift_and_rebuilds_edges`
- [x] Grep gate: `grep -rn "new_task_from_plan" aet-work/bin/sync` returns nothing
- [x] Skill-structure check passes with both SKILL.md edits
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Queues created in the interim carry `ready`/`blocked` states that the old code also understands; no data migration in either direction.

## Implementation Note

_Recorded by `aet-sync-docs` on 2026-07-10 — branch `frh-15-curated-flow-intake`._

This plan scoped an 8-file curated-intake implementation. The production semantics for **tasks 1–5** (`build_blocks` in `aet-work/lib/queue.py`, `add` parking at `ready`/`blocked` and rebuilding edges, `plan_parser` recording the real initial state, `sync` no longer auto-adding, and the explicit `aet-work add` handoff in both skill texts) were verified already present on `origin/main`, landed earlier via commit `a85ab7b` ("curated sprint intake"). This branch therefore delivered **task 6** — the regression contract (`test_add_parks_ready_when_unblocked`, `test_add_parks_blocked_with_pending_blockers_and_builds_edges`, `test_intake_history_records_actual_initial_state`, `test_sync_never_adds_new_plans`, `test_sync_still_reports_drift_and_rebuilds_edges`) — plus plan-footer bookkeeping. Feature behavior matches the plan; only the implementation locus differs (upstream commit rather than this branch). Task 7 (merge + verify) is owned by `aet-ship`.

---

_Stage: merged_
_Next step: run `aet-ship`_

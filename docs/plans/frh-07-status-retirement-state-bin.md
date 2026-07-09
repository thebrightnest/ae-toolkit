---
id: frh-07-status-retirement-state-bin
size: M
blocked_by:
  - frh-06-status-retirement-lib
pipeline: standard
---

# Plan: Retire `status` in aet-state and init-queue; Supersede fods-06

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G5)
- Continues frh-06 (lib/read side). This plan removes the write side and the dead state-adjacent commands, and formally supersedes `docs/plans/fods-06-migration-reconcile.md`.

In `aet-work/bin/aet-state`: `_apply_transition` writes the legacy key at `:313` and `:335`; `derive_status` (`:171-256`) speaks legacy vocabulary (`in-progress`, `unblocked`) which `cmd_audit`/`cmd_heal` then convert back and forth (`:497`, `:530`) and reads `task.get("status")` in its warnings block (`:245`); `cmd_sync_footers` (`:831-860`) writes a _stage_ string into the _status_ field and is referenced by no current skill; `cmd_archive` (`:795-828`) is a deprecated migration helper; `validate_transition:289-292` is unreachable (the legality check at `:277` always fires first because `LEGAL_TRANSITIONS["abandoned"]` is empty) and its `reason` parameter is never read. Remaining task-record `status` writers found during scope validation: `init-queue:120,131,140,198` (rebuild paths, plus the `status_to_state` import at `:30`/`:172`) and `sync:164-165` (`merge_verified` normalization).

> **Scope guard:** only the queue task record's legacy `status` key is retired. The **plan-frontmatter `status`** (`draft`/`approved`/`merged`/… — CONTEXT.md "Status (plan lifecycle)") is a different, live concept owned by `update_plan_frontmatter_status`/`aet-ship` and MUST NOT be touched.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. `aet-state`: remove both `task["status"] = ...` writes from `_apply_transition`; make `derive_status` return canonical states (`in_progress`, `ready`, …) and update `cmd_audit`/`cmd_heal` to compare states directly (no conversion round-trip) — M
2. `aet-state`: delete `cmd_sync_footers` + its subparser, `cmd_archive` + its subparser, the unreachable abandoned/`failure_reason` branch in `validate_transition`, and the unused `reason` parameter (the CLI `--reason` flag stays — it feeds history evidence in `cmd_transition`) — S
3. `init-queue`: rewrite all rebuild-path writes (`:120,131,140,198`) to set `state` only; simplify `preserve_task_metadata` to state-only vocabulary; drop the `status_to_state` import — M
4. `sync`: replace the `merge_verified` status normalization (`:164-165`) with state-based handling (or delete if frh-06's normalize-on-read already covers it); `lib/plan_parser.py`: drop the `status` field and parameter from `new_task_from_plan` (`:281-299`) and update its caller `add:115` — S
5. Supersede fods-06: set `docs/plans/fods-06-migration-reconcile.md` footer to `_Stage: superseded_` with a one-line note pointing at this plan and the owner decision (empty queue + shipped partition made the corpus migration moot) — S
6. Update tests: `tests/test_aet_state.py` (sync-footers/archive/vocabulary), `tests/test_init_queue_sync.py` — M
7. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks

## Files to Modify

- `aet-work/bin/aet-state`
- `aet-work/bin/init-queue`
- `aet-work/bin/sync`
- `aet-work/bin/add`
- `aet-work/lib/plan_parser.py`
- `docs/plans/fods-06-migration-reconcile.md` (supersession footer)
- `tests/test_aet_state.py`
- `tests/test_init_queue_sync.py`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] Named tests:
  - `test_apply_transition_writes_no_status_key` (in `tests/test_aet_state.py`)
  - `test_audit_and_heal_speak_canonical_states`
  - `test_sync_footers_command_removed` (subparser absent)
  - `test_init_queue_preserves_state_only_metadata` (in `tests/test_init_queue_sync.py`)
- [ ] Grep gate: `grep -rn "status_to_state\|state_to_status" aet-work/ aet-evolve/ aet-ship/` returns nothing; `grep -rn 'task\["status"\]\|task\.get("status")' aet-work/` returns nothing (plan-frontmatter `status` handling in `update_plan_frontmatter_status` is exempt and untouched)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; restore `.agents/work-archive.json` from git history if needed. fods-06's footer revert restores its prior stage.

---

_Stage: qa-complete_
_Next step: run `aet-review`_

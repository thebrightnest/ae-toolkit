---
id: frh-06-status-retirement-lib
size: M
blocked_by:
  - frh-01-locked-atomic-state-writes
pipeline: standard
---

# Plan: Retire the Legacy `status` Vocabulary — Queue Library and Read Side

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G5)
- Owner decision (2026-07-09): supersede fods-06's corpus migration; retire `status` directly. Live queue is empty; the live/settled partition (fods-07) already ships.

`lib/queue.py:49-73` carries the state↔status coexistence shim "until the migration in fods-06 retires status"; `:198-225` has `mark_status`/`mark_completed`/`mark_awaiting_merge` (zero non-test callers — already dead); `:294-392` has the archive helpers "superseded by settled history". Every module pays a dual-vocabulary tax.

Retirement mechanism: **normalize-on-read, never write.** `read_queue` upgrades legacy records in memory (`status`-only → set `state` from a single private literal mapping, drop `status`); `write_queue` never emits a `status` key. The public shim API is deleted. Settled history (`work-history.jsonl`) keeps historical keys untouched — append-only.

> **Scope guard:** only the queue task record's legacy `status` key is retired. The **plan-frontmatter `status`** (`draft`/`approved`/`merged`/… — CONTEXT.md "Status (plan lifecycle)") is a different, live concept owned by `update_plan_frontmatter_status`/`aet-ship` and MUST NOT be touched.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. `lib/queue.py`: add `_normalize_task` applied in `read_queue` (legacy `status` → `state` via one private literal dict; delete the `status` key; no-op for modern records); simplify `current_state` to read `state` only — M
2. `lib/queue.py`: delete `state_to_status`, `status_to_state`, `_STATE_TO_STATUS`, `_STATUS_TO_STATE`, `mark_status`, `mark_completed`, `mark_awaiting_merge`, and the entire archive-helpers section (`TERMINAL_STATUSES`, `read_archive`, `write_archive`, `archive_tasks`) — S
3. `aet-work/bin/status`: display the canonical state directly (drop the `state_to_status` import at `:19` and the conversion at `:44`) — S
4. Repo hygiene for the deleted archive layer: `git rm .agents/work-archive.json`; add it to `.gitignore` — S
5. Update read-side tests (`tests/test_aet_work_read_side.py`, new legacy-intake coverage) and drop shim-dependent fixtures from `tests/test_backends.py` — M
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks (frh-07 consumes the new lib surface)

## Files to Modify

- `aet-work/lib/queue.py`
- `aet-work/bin/status`
- `.agents/work-archive.json` (delete)
- `.gitignore`
- `tests/test_aet_work_read_side.py`
- `tests/test_backends.py` (drop shim-dependent fixtures if any)

## Validation Steps

- [x] `make validate` passes; full suite passes
- [x] Named tests (in `tests/test_aet_work_read_side.py`):
  - `test_read_queue_normalizes_legacy_status_records` (status-only record gains `state`, loses `status`)
  - `test_write_queue_never_emits_status_key`
  - `test_status_binary_displays_canonical_state`
- [x] Grep gate: `grep -rn "state_to_status\|status_to_state\|mark_completed\|mark_awaiting_merge\|mark_status" aet-work/lib aet-work/bin` returns no hits
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Normalize-on-read makes no destructive file changes until a write occurs; a reverted binary reads old and new queues alike (state keys are a superset).

---

_Stage: qa-complete_
_Next step: run `aet-review`_

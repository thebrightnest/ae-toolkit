---
id: fods-02-state-spine
blocked_by: []
size: L
---

# Plan: Forward-Only State Spine — `state`, `history[]`, and `transition` as Sole Writer

## Context

- PRD: `docs/prds/forward-only-deterministic-work-state-prd.md` (Workstream B, first half)
- ADR: `docs/adr/011-forward-only-deterministic-work-state.md` (decisions 1, 2, 6)
- Builds on: `fods-01-record-merge` (shipped). This is the **keystone** of ADR-011 — every other remaining plan depends on the schema and single-writer introduced here.

Today state is re-derived from git on every read (`aet-state derive`). This plan introduces the recorded-forward model: each task carries one `state` plus an append-only `history`, and **`aet-state transition` is the only code that writes `state`**, maintaining the "ready" frontier forward (no DAG re-walk).

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **State model + lifecycle constants in `aet-work/lib/queue.py`** — S

   Add `STATES = {planned, ready, blocked, in_progress, awaiting_merge, merged, abandoned, failed}`, `TERMINAL_STATES = {merged, abandoned}`, and a `LEGAL_TRANSITIONS` table (per the PRD lifecycle). Add a `append_history(task, frm, to, by, evidence=None)` helper writing `{from, to, at, by, evidence}`. New schema fields: `state`, `pending_blockers`, `history` (keep `blocks`).

2. **Rewrite `validate_transition` to the new lifecycle** — M (`aet-work/bin/aet-state`)

   Validate `from == task["state"]` and `to ∈ LEGAL_TRANSITIONS[from]`. Preserve the `merged` ancestry guard (branch/`merge_commit` on `origin/main`) — this is the one allowed git touch, and only at **write** time. Illegal transitions exit non-zero with a clear message and mutate nothing.

3. **`transition` becomes the sole writer: atomic write + history + forward frontier** — M (`aet-work/bin/aet-state`)

   On every transition: set `state`, append a history entry, write atomically. On a **terminal** transition (`merged`/`abandoned`): iterate the task's `blocks`, decrement each dependent's `pending_blockers`, and promote any dependent reaching `0` from `blocked`→`ready` (recording that promotion in the dependent's history, `by="release"`).

4. **Route `record-merge` through `transition`** — S (`aet-work/bin/aet-state`)

   `record-merge` resolves the SHA (existing logic from fods-01) and then performs the `awaiting_merge`→`merged` transition **through the sole writer**, so dependent promotion fires. No direct `state` writes remain outside `transition`.

5. **Unit tests** — M (`tests/test_aet_state.py`)

   - `test_legal_transition_matrix` / `test_illegal_transition_rejected_no_mutation`
   - `test_history_entry_shape`
   - `test_terminal_transition_promotes_dependent` (blocked dependent → ready; `pending_blockers` decremented)
   - `test_record_merge_drives_merged_and_promotes`

6. **Merge branch to main and verify integration** — S

## Coexistence note (locked-in)

`state` is introduced **alongside** the legacy `status` field; `status` is left untouched but is no longer scheduling truth. `fods-03` switches all readers to `state`; `fods-06`'s migration normalizes/retires legacy `status`. This keeps fods-02 independently shippable.

## Blocked by

None — this is the first task of the remaining work and builds on shipped `fods-01`.

## Validation Steps

- [ ] `aet-state transition` is the only function that assigns `task["state"]` (grep confirms no other writer).
- [ ] Terminal transition promotes a `blocked` dependent to `ready` and decrements `pending_blockers`.
- [ ] `record-merge` reaches `merged` only via `transition`.
- [ ] Named tests in `tests/test_aet_state.py` (above) cover legal/illegal/terminal/record-merge paths.
- [ ] `make validate` passes.

## Rollback Plan

Revert `aet-work/bin/aet-state` and `aet-work/lib/queue.py`. The legacy `status`/`derive` path is untouched, so the queue stays readable by current tooling.

---

_Stage: implemented_
_Next step: run `aet-qa`_

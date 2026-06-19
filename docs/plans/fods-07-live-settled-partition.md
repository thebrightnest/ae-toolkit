---
id: fods-07-live-settled-partition
blocked_by:
  - fods-03-read-path-zero-git
size: M
---

# Plan: Live/Settled Partition — Terminal Transition Seals to History

## Context

- PRD: `docs/prds/forward-only-deterministic-work-state-prd.md` (Workstream D)
- ADR: `docs/adr/011-forward-only-deterministic-work-state.md` (decisions 1, 7; revises ADR-009)

The live `.agents/work-queue.json` should hold only **non-terminal** tasks. When `fods-02`'s writer takes a task terminal (`merged`/`abandoned`), it appends the final record + history to an append-only `.agents/work-history.jsonl` and removes it from the live file — **atomically**. This is safe unconditionally because the task's forward effect on dependents already fired during the transition. `status`/`next` read the live set only, so operational cost stays bounded by work-in-flight regardless of project age.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **History-store helpers** — S (`aet-work/lib/queue.py`)

   `append_history_record(history_file, task)` (JSONL append) and `seal_terminal(queue_file, history_file, task_id)` which removes the task from live and appends it to settled in one atomic pass.

2. **Wire the terminal transition to seal** — M (`aet-work/bin/aet-state`)

   In `transition`, after a terminal transition's dependent promotion, seal the task (live → settled). Supersede the `work-archive.json` dedup path: keep `aet-state archive` as a deprecated alias that delegates to the seal (or no-ops with a message). Document the ADR-009 revision.

3. **Read the live set only** — S (`aet-work/bin/status`, `aet-work/bin/next`)

   Confirm both read only the live file (post-`fods-03`); settled history is never loaded for scheduling. A browsable view, if ever wanted, is derived from the log on demand.

4. **Tests** — M (`tests/test_queue.py`)

   - `test_terminal_seal_removes_from_live_and_appends_jsonl`
   - `test_no_id_in_both_live_and_settled` (invariant)
   - `test_dependents_promoted_before_seal`

5. **Merge branch to main and verify integration** — S

## Blocked by

- fods-03-read-path-zero-git

## Validation Steps

- [ ] A terminal transition removes the task from `work-queue.json` and appends it to `work-history.jsonl`.
- [ ] No task id appears in both the live file and the settled log (invariant test).
- [ ] `status`/`next` operate on the live set only.
- [ ] Dependents are already promoted at seal time (seal does not re-walk the DAG).
- [ ] `make validate` passes.

## Rollback Plan

Revert the seal helpers and the terminal-transition hook; re-enable `archive`/`work-archive.json`. Settled records remain in the JSONL log (append-only) and can be re-loaded if needed.

---

_Stage: reviewed_
_Next step: run `aet-sync-docs`_

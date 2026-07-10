---
id: frh-09-stage-telemetry-emission
size: M
blocked_by:
  - frh-08-dead-layer-deletion
pipeline: standard
status: merged
---

# Plan: Deterministic Stage Telemetry — Emit What the Guide Promises

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G6)
- Owner decision (2026-07-09): deterministic + derive. Code emits what code can know; `loop_record` is deleted as unknowable without session introspection.

`docs/telemetry-guide.md:19-26` promises task JSONL contains stage records, internal loops, test runs, and learning candidates — but `stage_record`, `loop_record`, `test_run_record`, and `learning_candidate_record` (`lib/telemetry.py:176-360`) have **zero call sites**. Only `run_summary` and `environment_issue` are written. The guide's `symlink_dependencies` example uses `from`/`to` keys while `worktree.py` requires `name`/`source`/`target` — a guaranteed failure for anyone following the guide.

Sessions vs stages: in `standard` isolation one session may span several stages, so per-stage timing inside a group is unknowable. The honest deterministic unit is the **session**: one `stage_record` per spawned session, with `stage` = the session's target stage and a new optional `stages` list capturing the span for group sessions. Full/minimal isolation yields exact per-stage records.

Blocked on frh-08 — last plan in the serialized orchestrator chain before this one.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. `lib/telemetry.py`: add optional `stages: list[str] | None` to `stage_record`; delete `loop_record`; drop the `loops` handling from `report()`/`_format_report` — S
2. `bin/orchestrator`: wrap `run_stage` and `run_stage_group` call sites with start/end capture and `logger.append_record(telemetry.stage_record(...))` — including failure exits — with `files_modified` (`git -C wt diff --name-only main...HEAD`) and `commits_created` (`rev-list --count`) computed post-session; `token_count`/`cost_estimate` stay `None` — M
3. `aet-evolve/bin/mine-learnings`: drop expectations for `loop` records; confirm it mines `stage` records as emitted — S
4. Rewrite `docs/telemetry-guide.md` "What gets recorded" to the emitted truth (stage sessions, environment issues, run summary); fix the `symlink_dependencies` example to `name`/`source`/`target` — S
5. Tests: extend/create `tests/test_telemetry.py` and `tests/test_orchestrator.py` coverage — M
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks

## Files to Modify

- `aet-work/lib/telemetry.py`
- `aet-work/bin/orchestrator`
- `aet-evolve/bin/mine-learnings`
- `docs/telemetry-guide.md`
- `tests/test_telemetry.py` (extend or create)
- `tests/test_orchestrator.py`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] Named tests:
  - `test_stage_record_emitted_per_session` (single-stage run → one record with exact stage)
  - `test_group_session_record_carries_stage_span` (`stages` list populated)
  - `test_failed_session_emits_failure_stage_record`
  - `test_report_has_no_loop_line`
- [ ] Grep gate: `grep -n "loop_record" aet-work/ aet-evolve/ -r` returns nothing
- [ ] Manual: run `aet-work run-one` on a trivial fixture plan; verify `~/.aet/telemetry/.../{task-id}.jsonl` contains `type: stage` records
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; telemetry returns to run-summary-only. Archive files are append-only JSONL — old readers skip unknown record types.

---

_Stage: merged_
_Next step: run `aet-cso`_

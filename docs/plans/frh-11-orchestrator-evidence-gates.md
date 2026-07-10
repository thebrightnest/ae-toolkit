---
id: frh-11-orchestrator-evidence-gates
size: M
blocked_by:
  - frh-09-stage-telemetry-emission
  - frh-10-gate-evidence-contract
pipeline: standard
---

# Plan: Orchestrator Gates Consume Evidence; Derive Test-Run Telemetry

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G6, G7)

With frh-10's evidence layer in place, the orchestrator can gate on machine-checkable verdicts instead of footer regex. Today the group-session path reads the plan footer to decide how far a session advanced (`orchestrator:393` `read_plan_stage`) — the footer is load-bearing for scheduling despite PIPELINE.md claiming otherwise. `_divergences_found` still reads `/tmp/aet-reports` (`pipeline.py:126-149`) with an unused `repo_root` binding.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. `run_stage`/`run_stage_group`: export `AET_EVIDENCE_PATH` (computed via `evidence.evidence_path`) plus `AET_TASK_ID`/`AET_RUN_ID` for top-level run-one sessions — S
2. Fail-closed gates: after a session covering a checking stage (qa/review/cso/sync-docs), require a schema-valid verdict with `verdict: "pass"`; missing, invalid, or failing verdict → stage failure (same path as nonzero exit). Group advancement is determined by which stages have valid verdicts — replacing the `read_plan_stage` scheduling read; footer remains a breadcrumb only — M
3. Derive telemetry: on a valid qa verdict, emit `telemetry.test_run_record` from its fields (`test_command`, counts); update `docs/telemetry-guide.md` with the derived record line — S
4. `pipeline.py`: rewrite `_divergences_found` to read review/cso/sync-docs verdicts (non-empty `findings`/`divergences`) from the evidence home; delete the unused `repo_root` binding and `/tmp` path — S
5. `ruff.toml`: remove the frh-04 per-file ignores (add the missing `Stage` import to the orchestrator's pipeline import while editing it) — S
6. Tests: extend `tests/test_orchestrator.py` and `tests/test_gate_evidence.py` — M
7. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks

## Files to Modify

- `aet-work/bin/orchestrator`
- `aet-work/lib/pipeline.py`
- `ruff.toml`
- `docs/telemetry-guide.md`
- `tests/test_orchestrator.py`
- `tests/test_gate_evidence.py`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] Named tests:
  - `test_gate_fails_closed_on_missing_verdict`
  - `test_gate_fails_on_schema_invalid_verdict`
  - `test_gate_fails_on_failing_verdict`
  - `test_group_advancement_determined_by_evidence_not_footer`
  - `test_qa_verdict_derives_test_run_record`
  - `test_divergences_found_reads_evidence_home`
- [ ] Grep gates: `grep -n "aet-reports" aet-work/lib/pipeline.py` returns nothing; `grep -n "read_plan_stage" aet-work/bin/orchestrator` only in breadcrumb/fallback display paths, not gating logic
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; gates fall back to footer-based behavior. Evidence files remain harmless artifacts.

---

_Stage: implemented_
_Next step: run `aet-qa`_

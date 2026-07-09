---
id: frh-10-gate-evidence-contract
size: M
blocked_by: []
pipeline: standard
---

# Plan: Structured Gate Evidence — Schemas, Home, and Writer Contract

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G7)
- Owner decision (2026-07-09): evidence lives at `~/.aet/reports/{project-slug}/{task-id}/{stage}.json`, mirroring telemetry's home + env-override pattern.

Today the pipeline knows a checking stage passed because an agent edited a `*Stage:*` footer that code regex-parses, and `_divergences_found` checks hardcoded `/tmp/aet-reports/{task_id}` (`pipeline.py:141`) — not portable, collides across projects, and no writer in this repo. This plan creates the evidence layer and the writer contract; orchestrator consumption is frh-11 (keeping the two file-disjoint: this plan touches no orchestrator/pipeline code).

Refinement vs PRD technical note: verdict schemas ship as Python literals in `lib/evidence.py` (one `SCHEMAS` dict) rather than separate JSON files — same checked-in visibility, stdlib validation either way, and it keeps the file count within task limits.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. New `aet-work/lib/evidence.py`: `reports_dir()` (default `~/.aet/reports`, `AET_REPORTS_DIR` override), `evidence_path(task_id, kind, project_slug=None)` (slug via `telemetry.derive_project_slug`), `write_verdict`, `read_verdict`, `validate_verdict(record, kind)` — required-keys/type checking, stdlib only — M
2. Define `SCHEMAS` for four verdict kinds — common core `{task_id, stage, skill, verdict: "pass"|"fail", summary, generated_at}` plus per-kind fields: `qa` (`test_command`, `tests_total`, `tests_passed`, `tests_failed`), `review` (`findings: list`), `cso` (`findings: list`), `sync-docs` (`divergences: list`) — S
3. Writer contract in the four checking skills — `aet-qa/SKILL.md`, `aet-review/SKILL.md`, `aet-cso/SKILL.md`, `aet-sync-docs/SKILL.md`: write the verdict JSON to `$AET_EVIDENCE_PATH` when set (orchestrated runs, frh-11) or to the documented default path otherwise, **before** updating the plan footer; footer stays a human breadcrumb — M
4. Tests: `tests/test_gate_evidence.py` (new) — M
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks (frh-11 consumes this surface)

## Files to Modify

- `aet-work/lib/evidence.py` (new)
- `aet-qa/SKILL.md`
- `aet-review/SKILL.md`
- `aet-cso/SKILL.md`
- `aet-sync-docs/SKILL.md`
- `tests/test_gate_evidence.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_gate_evidence.py` (unit, tmp dirs):
  - `test_valid_qa_verdict_passes_validation`
  - `test_missing_required_key_fails_validation`
  - `test_wrong_type_fails_validation`
  - `test_reports_dir_env_override`
  - `test_evidence_path_is_project_namespaced` (two slugs → distinct paths)
  - `test_write_then_read_verdict_roundtrip`
- [ ] Skill-structure check: `./scripts/validate-skills.sh` passes with the four SKILL.md edits
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Evidence files are additive artifacts outside the repo; no state depends on them until frh-11.

---

_Stage: reviewed_
_Next step: run `aet-sync-docs`_

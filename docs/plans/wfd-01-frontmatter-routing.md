---
id: wfd-01-frontmatter-routing
size: M
blocked_by:
  - rdm-01-decision-adrs
  - rdm-02-rtrace-templates
pipeline: standard
status: approved
security_review: required
security_review_reason: touches orchestrator gate logic — the security stage's own routing
docs_sync: required
docs_sync_reason: changes the plan frontmatter contract documented in skills and templates
---

# Plan: Dissolve the Pipeline Lambdas into Plan-Frontmatter Routing

## Context

- PRD: `docs/prds/roadmap-p1-workflow-as-data-prd.md` (G2; R-4, R-5, R-6)
- ADR-020 principle: route with judgment once at plan time, enforce with code forever. Doc 06 P2: runtime conditionals disappear from the workflow entirely — that is what makes pipeline-as-data possible.
- Ground truth: `aet-work/lib/pipeline.py:48,55` holds two lambdas backed by `_security_sensitive` (`:97-127`, filename-keyword heuristic) and `_divergences_found` (`:130-169`, evidence read). The orchestrator checks `.conditional` at `aet-work/bin/orchestrator:601-604` (group runnable filter) and `:696-699` (per-stage walk).
- This plan dissolves judgment while the stage table still exists; extraction of the table itself is a separate task (`wfd-02`/`wfd-03` in this PRD). After this plan, every field on `Stage` is serializable data.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `Stage.conditional: Callable` is replaced by `Stage.gate_key: str | None` (pure data). Assignments: stage `reviewed` (skills `aet-cso`) → `gate_key="security_review"`; stage `secure` (skills `aet-sync-docs`) → `gate_key="docs_sync"`; all other stages `None`.
- Skip resolution (orchestrator helper `stage_enabled(stage, plan_fm) -> bool`): a stage with `gate_key` runs unless the plan frontmatter sets that key to `skipped`. Missing key → `required` → the stage runs (fail-safe). Both call sites (`:601-604`, `:696-699`) use the helper; frontmatter is parsed once per task via `plan_parser.parse_frontmatter`.
- Frontmatter contract additions (values validated at intake): `security_review: required|skipped`, `docs_sync: required|skipped`; when a key is `skipped`, the matching `*_reason` key must be a non-empty string. Enforced in `plan_parser.intake_validation_errors` — for newly added plans only (the existing `limit_to` mechanism; already-queued plans are grandfathered and covered by the runtime default).
- `_security_sensitive` and `_divergences_found` are deleted. `aet-sync-docs` already no-ops safely when there are no divergences to reconcile; a skipped-security plan records why, at plan time, in the plan itself.
- Skill prose: `aet-plan` `create-stories` gains one step — set both keys deliberately on every plan with a one-line reason; `.agents/templates/plan-template.md` frontmatter example (as updated by rdm-02) gains the two keys.

## Rejected Alternatives

- Keep `_divergences_found` (deterministic evidence read, arguably not judgment) — rejected: P2 dissolves both; one skip mechanism beats two; the sync-docs skill no-ops cheaply.
- Default missing keys to `skipped` — rejected: silently skipping a security gate is the wrong failure direction; fail-safe = run.
- Enforce the new keys on all existing plans at sync time — rejected: retroactive intake errors would poison the already-approved rdm queue entries; the runtime default covers them.
- Compile the routing keys into the task record at `aet-work add` (purist ADR-011 forward-consumption) — rejected for now: single-plan mode (`--plan-file`, no queue) has no task record, and the `pipeline:` isolation key sets the runtime-frontmatter precedent; the keys are validated machine contract (ADR-011 point 4), policy input rather than state. Revisit when `aet desk` (roadmap Phase 4) wants routing visible on the queue.

## Task List

1. `aet-work/lib/pipeline.py`: replace `conditional` with `gate_key` on `Stage`; set `gate_key` on `reviewed`/`secure`; delete `_security_sensitive`, `_divergences_found`, and now-unused imports — S (traces: R-5)
2. `aet-work/bin/orchestrator`: add `stage_enabled(stage, plan_fm)`; parse plan frontmatter once per task; replace both `.conditional` call sites; print the skip decision with its source (`frontmatter` vs `default`) — M (traces: R-5)
3. `aet-work/lib/plan_parser.py`: validate `security_review`/`docs_sync` values and skipped-requires-reason in `intake_validation_errors` (newly added plans only, via `limit_to`) — S (traces: R-4)
4. `aet-plan/SKILL.md` (`create-stories` step) + `.agents/templates/plan-template.md` frontmatter example: both keys set deliberately with recorded reasons — S (traces: R-6)
5. Tests: extend `tests/test_pipeline.py` (gate_key present, conditional gone), `tests/test_orchestrator.py` (skip on `skipped`, run on missing key, run on `required`), `tests/test_init_queue_sync.py` (invalid value rejected; skipped-without-reason rejected; grandfathered plans pass) — M (traces: R-4, R-5)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition — engine gate-logic change warranting isolated review
- [x] Diff expected > 3 files (8 files)
- [x] Cannot share a branch: `wfd-02` is parallel-safe by design (new files only); merging them would serialize the batch

## Files to Modify

- `aet-work/lib/pipeline.py`
- `aet-work/bin/orchestrator`
- `aet-work/lib/plan_parser.py`
- `aet-plan/SKILL.md`
- `.agents/templates/plan-template.md`
- `tests/test_pipeline.py`
- `tests/test_orchestrator.py`
- `tests/test_init_queue_sync.py`

## Validation Steps

- [ ] `make validate` passes (ruff + pytest + skill checks)
- [ ] Named tests per changed surface: `tests/test_pipeline.py` (unit: Stage.gate_key), `tests/test_orchestrator.py` (integration: frontmatter-driven skip/run across group and per-stage paths), `tests/test_init_queue_sync.py` (unit: intake contract)
- [ ] `grep -rn "_security_sensitive\|_divergences_found\|conditional" aet-work/` returns no engine hits
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — the frontmatter keys are additive and ignored by the reverted engine; no queue or data migration involved.

---

_Stage: implemented_
_Next step: run `aet-qa`_

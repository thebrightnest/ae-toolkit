---
id: ppt-02-aet-plan-skill
size: S
status: queued
blocked_by: []
pipeline: minimal
security_review: required
security_review_reason: skill-text change only, no code paths touched
docs_sync: required
docs_sync_reason: PRD footer must reflect skill updates
---

# Plan: aet-plan Skill Pipeline Guidance

## Context

Update `skills/aet-plan/SKILL.md` frontmatter contract so plan authors set `pipeline` using the size-based default plus risk override. See PRD: docs/prds/pipeline-performance-telemetry-prd.md

## Intake Triage

- [ ] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Update the `pipeline` frontmatter explanation in `skills/aet-plan/SKILL.md` to state the size-based default (S→minimal, M→standard, L→standard/full) and the risk override rule. — S (traces: R-3)
2. Add a reference to ADR-047 in the frontmatter contract section. — S
3. Verify markdownlint and skills-lint pass. — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 100 expected diff lines
- **M**: ≤ 1 day human time / ≤ 200 expected diff lines
- **L**: > 1 day OR > 200 lines — re-evaluate against the full guardrail model; split only if a limit is actually exceeded

## Rejected Alternatives

- **Auto-default in orchestrator** — rejected: size is a measurement, not a gate (ADR-046). Convention-first keeps the decision visible in the plan file.

## Files to Modify

- `skills/aet-plan/SKILL.md`

## Validation Steps

- [ ] `make validate` passes
- [ ] Skill structure validator passes (`scripts/validate-skills.sh`)

## Rollback Plan

Revert `skills/aet-plan/SKILL.md` to the previous commit.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and
dependency changes should usually use `standard` or `full`.

---

*Stage: qa-complete*
*Next step: run `aet-review`*

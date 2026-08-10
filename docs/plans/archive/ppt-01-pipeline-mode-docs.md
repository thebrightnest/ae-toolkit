---
id: ppt-01-pipeline-mode-docs
size: M
status: merged
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: docs change only, no code paths touched
docs_sync: required
docs_sync_reason: PRD footer must reflect doc updates
---

# Plan: Pipeline Mode Docs & Template

## Context

Update `docs/PIPELINE.md` and `.agents/templates/plan-template.md` to codify the size-based pipeline defaults from ADR-047. See PRD: docs/prds/pipeline-performance-telemetry-prd.md

## Intake Triage

- [ ] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. ✓ Add a "Pipeline Mode Selection" section to `docs/PIPELINE.md` with a size-to-mode table (S→minimal, M→standard, L→standard/full) and the risk override list (auth, data-model, API, dependencies, infrastructure). — M (traces: R-1)
2. ✓ Update `.agents/templates/plan-template.md` frontmatter comment to explain the size-based default and link to `docs/PIPELINE.md`. — S (traces: R-2)
3. ✓ Update ADR-047 status from Proposed to Accepted and verify it is referenced from `docs/PIPELINE.md`. — S (traces: R-4)
4. ✓ Verify markdownlint passes on both files. — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 100 expected diff lines
- **M**: ≤ 1 day human time / ≤ 200 expected diff lines
- **L**: > 1 day OR > 200 lines — re-evaluate against the full guardrail model; split only if a limit is actually exceeded

## Rejected Alternatives

- **Bundle skill-text changes here** — rejected: `skills/aet-plan/SKILL.md` is a separate subsystem (skills) and would exceed the 2-subsystem guardrail.

## Files to Modify

- `docs/PIPELINE.md`
- `.agents/templates/plan-template.md`

## Validation Steps

- [ ] Lint passes (`make lint`)
- [ ] Both files reference ADR-047
- [ ] Risk override list matches ADR-047

## Rollback Plan

Revert the two doc files to the previous commit.

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

*Stage: merged*
*Next step: run `aet-work`*

---

*Stage: merged*

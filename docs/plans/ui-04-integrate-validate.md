# Plan: ui-04 — Integrate aet-validate-ui into Toolkit + Validate & Package

## Context

- PRD: `docs/prds/aet-validate-ui-prd.md`
- All skill files are written from previous tasks.
- This is the final integration step.

## Tasks

1. Update `README.md` — add `aet-validate-ui` to the skills table with description and link.
2. Run `make format` to ensure consistent markdown formatting.
3. Run `make validate` (lint + format-check + skill-structure checks).
4. Run `make package` to generate `aet-validate-ui.skill`.
5. Update `.agents/work-queue.json` to mark all `ui-*` tasks as done (if running manually) or verify the queue state.

## Dependencies

- Blocked by `ui-01-scaffold-skill`
- Blocked by `ui-02-write-skill-core`
- Blocked by `ui-03-write-examples-references`

## Validation Steps

- [ ] `README.md` includes `aet-validate-ui` in the skill table
- [ ] `make validate` passes with zero errors
- [ ] `make package` produces `aet-validate-ui.skill`
- [ ] `aet-validate-ui.skill` is a valid zip archive containing the skill directory

## Rollback Plan

Revert `README.md`, delete `aet-validate-ui.skill`, and re-run `make validate`.

---

\*Stage: plan-approved\*\*\*

\*Next step: run `aet-pipeline-implement` or `aet-work`\*

# Plan: pp-01 — Integrate aet-validate-ui into aet-pipeline-plan

## Context

- **PRD:** `docs/prds/aet-validate-ui-prd.md` (Integration point section)
- **Current state:** `aet-pipeline-plan/SKILL.md` defines a 3-step pipeline:

  ```
  Step 1: aet-discover
      ↓ [HARD GATE]
  Step 2: aet-plan
      ↓ [HARD GATE: PRD approved]
  Step 3: aet-validate-scope
      ↓ [OUTPUT]
  ```

- **Target state:** Insert `aet-validate-ui` as Step 3, shifting `aet-validate-scope` to Step 4.
- **Reference:** `aet-validate-ui/SKILL.md` defines skip conditions (API-only, CLI-only, no UI) and rating/severity semantics.

## Locked-In Architecture Decisions

1. **aet-validate-ui is a hard gate.** If the gap report contains `blocking` severity findings, the pipeline stops for human decision. Warnings are surfaced but do not halt.
2. **Skip logic is mandatory.** If the PRD explicitly marks the feature as "no UI" (API-only, CLI-only, pure backend), the pipeline prints a skip notice and jumps directly to `aet-validate-scope`.
3. **Same resumability contract.** The pipeline stage footer system must support the new step. `aet-validate-ui` does not write a footer stage; it appends its report path to the PRD footer.
4. **No new files created.** This change is a surgical edit to `aet-pipeline-plan/SKILL.md` only.

## Tasks

1. **Update description and frontmatter** — update the `description` field to mention UI validation. — S
2. **Update pipeline sequence diagram** — expand from 3 to 4 steps, add aet-validate-ui between aet-plan and aet-validate-scope. — S
3. **Add Step 3 (aet-validate-ui) procedure** — include skip logic, report generation, hard gate for blocking findings, and PRD footer annotation. — M
4. **Update Step 4 (aet-validate-scope)** — renumber from Step 3, update cross-references. — S
5. **Update resume-from-stage table** — add `ui-validated` stage and map it to `aet-validate-scope`. — S
6. **Update completion protocol** — mention UI gap report in output artifacts. — S
7. **Update key principles** — add UI validation lockout / skip principle. — S
8. **Run `make validate`** — lint, format-check, skill-structure validator. — S
9. **Run `make package`** — regenerate `aet-pipeline-plan.skill`. — S

## Dependencies

- None (this is a self-contained skill edit).
- `aet-validate-ui` skill must exist (it does).

## Validation Steps

- [ ] `aet-pipeline-plan/SKILL.md` mentions aet-validate-ui in description
- [ ] Pipeline sequence shows 4 steps with aet-validate-ui as Step 3
- [ ] Step 3 includes skip logic for no-UI features
- [ ] Step 3 includes hard gate for blocking findings
- [ ] Resume table maps `ui-validated` to Step 4
- [ ] `make validate` passes with zero errors
- [ ] `make package` produces updated `aet-pipeline-plan.skill`
- [ ] `aet-pipeline-plan/SKILL.md` remains under 400 lines

## Rollback Plan

Revert `aet-pipeline-plan/SKILL.md` to the previous git revision and re-run `make package`.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_

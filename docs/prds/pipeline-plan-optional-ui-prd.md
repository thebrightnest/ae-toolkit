# PRD: Optional UI Validation in aet-pipeline-plan

## Overview

Currently, `aet-pipeline-plan` always runs `aet-validate-ui` as Step 3 unless the PRD carries an explicit "no UI" marker. In practice, many ideas are API-only, CLI-only, or backend-focused, and forcing UI validation adds friction. This change makes UI validation opt-in via an explicit trigger in the user's request or a prompt at the PRD approval gate.

## Goals

- Reduce friction for non-UI planning sessions by skipping UI validation by default.
- Preserve the ability to run UI validation when the user explicitly asks for it.
- Maintain backward compatibility: the "no UI" PRD marker still auto-skips.

## Non-Goals

- Changing the behavior of the standalone `aet-validate-ui` skill.
- Adding new files, templates, or CLI flags outside natural-language triggers.
- Modifying any other pipeline or planning skill.

## User Stories

- As a user planning a backend-only feature, I want the pipeline to skip UI validation so that I reach scope validation faster.
- As a user planning a UI-heavy feature, I want to trigger UI validation explicitly so that coverage gaps are caught before implementation.

## Acceptance Criteria

- [ ] `aet-pipeline-plan/SKILL.md` is updated so Step 3 is conditional.
- [ ] UI validation runs if the user request contains an explicit UI validation trigger (e.g., "with UI", "validating UI", "run UI validation").
- [ ] If no trigger is present, the PRD approval gate asks whether to run UI validation.
- [ ] If the user declines or the PRD is marked "no UI", Step 3 is skipped and the pipeline proceeds to Step 4.
- [ ] The skill description, sequence diagram, completion protocol, and key principles are updated to reflect the optional nature of UI validation.
- [ ] `make validate` passes after the change.

## Technical Notes

- The change is a single-file edit to `aet-pipeline-plan/SKILL.md`.
- No code or script changes are required.
- The trigger detection is natural-language based (case-insensitive keyword match).

## Open Questions

- None.

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_

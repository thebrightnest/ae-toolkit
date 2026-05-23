# PRD: Remove aet-discover from aet-pipeline-plan

## Overview

Make `aet-pipeline-plan` start directly at `aet-plan`, removing the mandatory `aet-discover` step. This separates product validation (discover) from technical planning (pipeline-plan), allowing users to run the full planning workflow for known tasks and fixes without forced PM gatekeeping. `aet-discover` remains fully intact as a standalone skill for raw ideas.

## Goals

- Remove `aet-discover` from the `aet-pipeline-plan` sequence
- Update `aet-pipeline-plan` description and triggers to reflect planning for validated work, not raw ideas
- Update `aet-pipeline-plan` resume logic to remove the `brief-validated` stage coupling
- Update `aet-pipeline-plan` completion protocol and output list to stop referencing product briefs
- Keep `aet-discover` skill 100% unchanged — it remains a standalone pre-step for unvalidated ideas
- Ensure `make validate` passes after all edits

## Non-Goals

- Do not modify `aet-discover` skill content, examples, or references
- Do not modify `aet-plan` skill content
- Do not create a new pipeline skill or new commands
- Do not change the optional `aet-validate-ui` step behavior
- Do not modify any application source code

## User Stories

- As a developer with a known bug or direct task, I want to run `aet-pipeline-plan` without `aet-discover` so I can get to planning and scope validation immediately.
- As a product owner with a raw unvalidated idea, I can still run `aet-discover` standalone and then hand off to `aet-plan` or `aet-pipeline-plan` when ready.
- As an AI agent executing `aet-pipeline-plan`, I no longer force the user through YC-style forcing questions when they already know what they want to build.

## Acceptance Criteria

- [ ] `aet-pipeline-plan/SKILL.md` sequence is updated to: `aet-plan` → `aet-validate-ui` (optional) → `aet-validate-scope`
- [ ] `aet-pipeline-plan/SKILL.md` description no longer references "raw idea" as the entry point
- [ ] `aet-pipeline-plan/SKILL.md` triggers updated to match planning for known/validated work
- [ ] `aet-pipeline-plan/SKILL.md` Step 1 (aet-discover) and its hard gate are removed entirely
- [ ] `aet-pipeline-plan/SKILL.md` resume table no longer references `brief-validated` as a resume stage
- [ ] `aet-pipeline-plan/SKILL.md` completion protocol no longer lists `docs/product-briefs/` as an output
- [ ] `aet-pipeline-plan/SKILL.md` Step 0 preamble updated to remove `EXISTING_BRIEFS` from collected context
- [ ] `aet-discover/SKILL.md` is untouched
- [ ] `AGENTS.md` updated if it references the old pipeline-plan behavior
- [ ] `make validate` passes
- [ ] `make package` regenerates `.skill` files

## Technical Notes

- This is a documentation-only change to skill markdown files.
- The `.skill` artifact is a zip of the skill directory — it will auto-update on `make package`.
- The `aet-plan` skill already contains the guardrail: _"If you have an unvalidated idea — run aet-discover first."_ This provides the discover → plan handoff without forcing it.

## Open Questions

- Should `aet-pipeline-plan` still collect `EXISTING_BRIEFS` context as a hint (even though it doesn't run discover), or remove it from the shared preamble entirely?
- Should we add a brief note in `aet-pipeline-plan` like: _"If you have not yet validated this idea, run `aet-discover` first"_ to preserve discoverability?

---

_Stage: prd-approved_
_Next step: run `aet-validate-scope`_

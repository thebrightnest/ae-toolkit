# PRD: Plan Quality Gates

## Overview

The plan is treated as infallible authority, but it has no internal consistency check. The FK existed in plan prose but not in the code block — the implement agent followed the code block into a bug. CSS was absent from the plan, so implement didn't write it and review's "Completeness vs plan" lens passed broken work. The wrong session ID was in the code block — followed verbatim into silent data loss.

This PRD adds **plan self-consistency validation**, requires `aet-implement` to reconcile prose against code blocks, and redefines review completeness as behavior delivered rather than tasks ticked.

## Goals

1. **Plan self-consistency lint** — at plan completion or `aet-validate-scope`: every constraint in prose appears in code blocks; every file in "files to modify" appears in a task; every acceptance criterion is an observable behavior, not a task restatement.
2. **Implement reconciles instead of obeying** — `aet-implement` treats prose and code blocks as two witnesses. Where they disagree, stop and flag — never silently follow the code block.
3. **Completeness = behavior delivered** — review's Completeness lens verifies against acceptance criteria with the question: "If I exercised this as the user, what would I see?" This catches missing CSS, missing endpoints, and missing error states even when the plan never mentioned them.
4. **Fold `aet-validate-ui` into `aet-validate-scope`** — the weakest skill (keyword matching against seven categories) becomes a lens within plan validation, not a standalone skill with its own trigger surface.

## Non-Goals

- Rewriting the plan format. We lint the existing format, not replace it.
- Automatic plan repair. The lint flags inconsistencies; humans (or the planning agent) fix them.
- Adding new planning stages. This is validation, not bureaucracy.

## User Stories

- As a plan reviewer, I want to know that every constraint mentioned in prose is actually represented in the code blocks before the plan is approved.
- As an implementer, I want the skill to stop me when the prose says one thing and the code block says another, rather than silently following the code block.
- As a code reviewer, I want the Completeness lens to ask "what would the user see?" so missing UI or error states are caught even when the plan omitted them.

## Acceptance Criteria

- [ ] `aet-plan/SKILL.md` or `aet-validate-scope/SKILL.md` includes the self-consistency lint procedure.
- [ ] Lint checks: (a) prose constraints appear in code blocks, (b) all "files to modify" are assigned to tasks, (c) acceptance criteria are observable behaviors.
- [ ] `aet-implement/SKILL.md` updated to require reconciliation when prose and code blocks disagree.
- [ ] `aet-review/SKILL.md` Completeness lens updated to behavior-oriented verification question.
- [ ] `aet-validate-ui/SKILL.md` removed; its checklist merged into `aet-validate-scope/SKILL.md` as a lens.
- [ ] `aet-validate-scope` stays under 400 lines after merge; excess detail moves to `references/`.

## Open Questions

1. Should the self-consistency lint be a hard block (plan cannot be approved until clean) or a warning flag?
2. Should `aet-implement` reconciliation be a hard stop or a flag-for-human decision?
3. Where does the merged `aet-validate-ui` checklist live — inline in `aet-validate-scope` or as a reference document?

---

*Stage: scope-validated*
*Validated: 2026-06-10*
*Notes: No conflicts. aet-validate-ui merge must not lose its checklist content — migrate to aet-validate-scope/references/. Self-consistency lint should run as part of aet-plan completion, not as a separate gate.*

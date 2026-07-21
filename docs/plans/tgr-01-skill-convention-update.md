---
id: tgr-01-skill-convention-update
size: M
blocked_by: []
pipeline: standard
status: draft
security_review: required
security_review_reason: Changes skill instructions that control how agents scope work; mis-scoping can affect security-sensitive changes.
docs_sync: required
docs_sync_reason: Updates conventions and templates that are consumed as documentation.
---

# Plan: Update Skill Instructions and Conventions for Revised Task Size Guardrails

## Context

- PRD: `docs/prds/task-size-guardrails-revision-prd.md`
- This plan revises the documented guardrails in the skills and conventions that agents read during planning.
- It does not change code; code changes are in `tgr-02-validator-test-update`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Update `skills/aet-plan/SKILL.md` guardrail section — M (traces: R-1, R-2, R-3, R-4, R-5)
2. Update `skills/aet-pipeline-plan/SKILL.md` guardrail references — S (traces: R-2)
3. Update `docs/CONVENTIONS.md` Task Size Guardrails section — M (traces: R-2, R-3, R-4)
4. Update `.agents/templates/plan-template.md` limits reference — S (traces: R-2, R-3, R-4)
5. Add revision note to `docs/prds/task-size-guardrails-prd.md` — S (traces: R-7)
6. Run `make validate` — S (traces: R-6)

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

If a task exceeds the agent session limit, split it into subtasks and document the relationship with `Split from: {parent-task-id}`.

### Renderer / UI Tasks (if applicable)

- [ ] Not applicable — no UI changes.

### Batching Check

Before finalizing this plan, confirm it should not be merged with related plans:

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks (code validator changes are separate).

## Rejected Alternatives

- **Keep a high file-count backstop (e.g., 20 files) in the validator** — rejected: it would reintroduce the same proxy problem the revision is trying to solve. Diff-line limit plus coherence guidance is sufficient.
- **Update the code validator in this plan** — rejected: mixing skill/docs changes with code changes would exceed the session-complexity target and blur review scope. Validator changes are isolated in `tgr-02-validator-test-update`.

## Files to Modify

- `skills/aet-plan/SKILL.md`
- `skills/aet-pipeline-plan/SKILL.md`
- `docs/CONVENTIONS.md`
- `.agents/templates/plan-template.md`
- `docs/prds/task-size-guardrails-prd.md`

## Validation Steps

- [ ] `make validate` passes
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] No new source files introduced by this plan
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

- Revert the modified skill/docs files from git and re-run `make validate`.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and dependency changes should usually use `standard` or `full`.

---

_Stage: plan-draft_
_Next step: run `aet-validate-scope`, then `aet-work`_

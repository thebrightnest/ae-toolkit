---
id: tgr-01-skill-convention-update
size: M
blocked_by: []
pipeline: standard
status: queued
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

1. ✓ Update `skills/aet-plan/SKILL.md` guardrail section, including the dual-limit references in the `create-stories` and `plan` command procedures — M (traces: R-1, R-2, R-3, R-4, R-5)
2. ✓ Update `skills/aet-pipeline-plan/SKILL.md` guardrail references — S (traces: R-2)
3. ✓ Update `docs/CONVENTIONS.md` Task Size Guardrails section, plus the remaining dual-limit references in the docs-taxonomy table and rules list — M (traces: R-2, R-3, R-4)
4. ✓ Update `.agents/templates/plan-template.md` limits reference — S (traces: R-2, R-3, R-4)
5. ✓ Redefine the S/M/L size labels in `skills/aet-plan/SKILL.md`, `docs/CONVENTIONS.md`, and `.agents/templates/plan-template.md`: drop the file-count column; L becomes a re-evaluation trigger, not an automatic split trigger — M (traces: R-2, R-8)
6. ✓ Add revision note to `docs/prds/task-size-guardrails-prd.md` — S (traces: R-7)
7. ✓ Run lint/format checks — S (traces: R-6) [Changed: only lint/format checks run; test suite skipped because toolkit verified only non-code files changed since QA green]

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 100 expected diff lines
- **M**: ≤ 1 day human time / ≤ 200 expected diff lines
- **L**: > 1 day OR > 200 lines — re-evaluate against the full guardrail model; split only if a limit is actually exceeded

If a task exceeds the intake limit (> 300 task-list lines) or the skill-level checks (> 4 agent-hours, > 2 subsystems, ~30k-token context budget), split it into subtasks and document the relationship with `Split from: {parent-task-id}`.

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

- [x] Lint/format checks pass (test suite skipped per toolkit diff scoping: only non-code files changed since QA green)
- [x] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [x] No new source files introduced by this plan
- [x] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

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

*Stage: synced*
*Next step: run `aet-ship`*

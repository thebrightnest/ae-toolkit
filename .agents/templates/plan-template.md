---
id: [plan-id]
size: [S/M/L]
blocked_by:
  - [blocker-plan-id]
pipeline: standard
status: draft
security_review: required
security_review_reason: [one line]
docs_sync: required
docs_sync_reason: [one line]
---

<!-- `status` is the plan lifecycle value (CONTEXT.md): one of `draft`,
`approved`, `queued`, `in_progress`, `awaiting_merge`, `merged`, `abandoned`. -->

<!-- `security_review` / `docs_sync` route the aet-cso and aet-sync-docs
pipeline gates at plan time: `required` (default) runs the stage; `skipped`
skips it and must be paired with the one-line reason above. A missing key is
treated as `required` (fail-safe — the stage runs). -->

# Plan: [Feature Name]

## Context

Link to the PRD and any relevant prior decisions.

## Intake Triage

- [ ] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Task description — S (traces: R-1)
2. Task description — M (traces: R-2)
3. Task description — S (traces: R-1, R-3)
4. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

If a task exceeds the agent session limit (≤ 4 hr / ≤ 8 files / ≤ 300 lines), split it into subtasks and document the relationship with `Split from: {parent-task-id}`.

### Renderer / UI Tasks (if applicable)

- [ ] Create/update renderer component(s)
- [ ] Add/update CSS styles for all custom `className` values
- [ ] Verify no unstyled `className` references remain

### Batching Check

Before finalizing this plan, confirm it should not be merged with related plans:

- [ ] This is not one of several near-identical additions (templates, examples, docs).
- [ ] The diff is expected to exceed 3 files or 50 lines.
- [ ] The work cannot share a branch/PR with related tasks.

If all boxes are unchecked, consider batching this work into a single plan.

## Rejected Alternatives

Record each alternative that was seriously considered for this plan and the
reason it was not chosen, so settled decisions do not silently re-open.

- **[Alternative A]** — rejected: [reason — e.g., duplicates a later phase;
  higher cost for no added signal; contradicts ADR-NNN.]
- **[Alternative B]** — rejected: [reason.]

## Files to Modify

- `path/to/file`
- `path/to/file`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] For each new source file introduced by this plan, name the test that will cover it
- [ ] Distinguish test types: unit tests (single layer), integration tests (cross-layer), API boundary tests (frontend ↔ backend contract)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

How to undo this change if something goes wrong.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet-work run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and
dependency changes should usually use `standard` or `full`.

---

_Stage: plan-approved_

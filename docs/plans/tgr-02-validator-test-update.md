---
id: tgr-02-validator-test-update
size: M
blocked_by:
  - tgr-01-skill-convention-update
pipeline: standard
status: approved
security_review: required
security_review_reason: Validator changes determine which plans are allowed into the work queue; misalignment could admit oversized tasks.
docs_sync: required
docs_sync_reason: Validator behavior change must be reflected in the docs updated by tgr-01 before this plan ships.
---

# Plan: Align Code Validator and Tests with Revised Task Size Guardrails

## Context

- PRD: `docs/prds/task-size-guardrails-revision-prd.md`
- Parent plan: `docs/plans/tgr-01-skill-convention-update.md`
- This plan aligns the intake validator and its tests with the revised guardrails documented in the skills and conventions.
- It is blocked by `tgr-01` so the documented model is settled before the code changes.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Update `src/aet/plan_parser.py` `validate_size()` to drop the file-count intake limit and remove the now-unused `count_files_to_modify()` — M (traces: R-2, R-3, R-6)
2. Update `tests/queue/test_init_queue_sync.py` to match the revised validator behavior, including a new test pinning that a plan listing more than 8 files but ≤ 300 task-list lines is accepted — M (traces: R-2, R-6)
3. Run `make test` and `make validate` — S (traces: R-6)

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
- [x] The work cannot share a branch/PR with tgr-01 because it changes source code and tests separately from skill/docs text.

## Rejected Alternatives

- **Keep a high file-count backstop (e.g., 20 files) in the validator** — rejected: it would reintroduce the same proxy problem the revision is trying to solve and contradict the updated skill instructions.
- **Merge this work into tgr-01** — rejected: tgr-01 is already at the upper bound of a reviewable docs/skill change; adding validator and test changes would make the diff too broad.

## Files to Modify

- `src/aet/plan_parser.py`
- `tests/queue/test_init_queue_sync.py`

## Validation Steps

- [ ] `make test` passes
- [ ] `make validate` passes
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] No new source files introduced by this plan; existing `validate_size()` behavior remains under test
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

- Revert `src/aet/plan_parser.py` and `tests/queue/test_init_queue_sync.py` from git and re-run `make test` / `make validate`.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and dependency changes should usually use `standard` or `full`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_

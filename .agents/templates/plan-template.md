---
id: [plan-id]
size: [S/M/L]
work_class: [trivial/normal/critical]
blocked_by:
  - [blocker-plan-id]
pipeline: standard
security_review: required
security_review_reason: [one line]
docs_sync: required
docs_sync_reason: [one line]
# Optional identity declarations for plans that conflate two identifiers for
# the same entity. Required when the identity-conflation lens fires; omitted
# otherwise. Each entry names the entity, the conflated identifiers, and which
# one persists. Example:
# identity:
#   - entity: project
#     identifiers: [projectPath, projectId]
#     persists: projectId
---

<!-- `work_class` is the risk/impact dimension `aet metrics` buckets by
(`plan_parser.py`): one of `trivial`, `normal`, `critical`. It is the only
source of that value — an omitted key records `unclassified`, and a queue of
unclassified tasks makes the per-class breakdown in `aet metrics` and
`aet retro` permanently empty. Choose one; do not leave the placeholder. -->

<!-- `status` has been removed from the plan frontmatter contract (ADR-055).
     Stage and settled-ness live in the ledger and task record, not in plan
     frontmatter. -->

<!-- `pipeline` selects the orchestrator isolation mode. Size-based defaults:
     S → minimal, M → standard, L → standard or full. Override to standard/full
     for auth, data-model, API, dependency, or infrastructure changes.
     See docs/PIPELINE.md#pipeline-mode-selection. -->

<!-- `security_review` / `docs_sync` route the aet-cso and aet-sync-docs
pipeline gates at plan time: `required` (default) runs the stage; `skipped`
skips it and must be paired with the one-line reason above. A missing key is
treated as `required` (fail-safe — the stage runs). `required` and `skipped`
are the *only* accepted values — a conditional or hedged value such as
`conditional` fails `aet plan validate`. If a stage's need depends on the
outcome of the work, declare `required` and say so in the reason. -->

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

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 1 day OR > 600 lines — re-evaluate against the full guardrail model; justify above 1500

If a task exceeds two or more of the skill-level checks (> 600 expected diff lines, > 1 human-day, > 2 implementation subsystems, ~60k-token context budget), split it into subtasks and document the relationship with `Split from: {parent-task-id}`. No plan-time proxy for diff size is enforced at intake (ADR-046).

### Renderer / UI Tasks (if applicable)

- [ ] Create/update renderer component(s)
- [ ] Add/update CSS styles for all custom `className` values
- [ ] Verify no unstyled `className` references remain

### Floor Check

Before finalizing this plan, confirm it should not be merged with a sibling plan. A plan is a floor candidate when **two or more** of the following signals are true. One checked box is a prompt to justify the shape in writing; two or more means merge unless you can explain why not.

- [ ] Expected diff is below the calibrated floor threshold (≤ 50 headline lines; see `docs/CONVENTIONS.md`).
- [ ] The change is limited to one subsystem and maintains no architectural invariant.
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against (`blocked_by` that sibling, or blocked by it transitively).
- [ ] This is docs-only and its sole consumer is a single sibling.

If two or more boxes are checked, merge this work into a sibling plan instead. This check is advisory — it prompts a written justification, it does not block at scope validation.

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
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and
dependency changes should usually use `standard` or `full`.

---

_Stage: plan-approved_

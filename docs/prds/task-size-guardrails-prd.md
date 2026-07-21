# PRD: Task Size Guardrails for Agentic Planning

## Overview

Introduce enforceable size limits into all AE Toolkit planning skills so that no task entering the work queue exceeds what a single AI coding session can reliably execute. The guardrail uses a dual-limit model (human-time + AI-complexity) and auto-splits oversized tasks recursively. This prevents the dominant failure mode of agentic planning: tasks so large that sessions bloat, context degrades, and output quality collapses before completion.

## Goals

- **G1:** Ensure every task that reaches `docs/plans/*.md` or `.agents/work-queue.json` is implementable in a single agent session without context exhaustion.
- **G2:** Eliminate "human-scale" estimates (days/weeks) at the plan-task level by forcing AI-complexity awareness into every split decision.
- **G3:** Reduce plan revision cycles caused by mid-implementation realization that a task was too big.
- **G4:** Make the guardrail automatic — the agent splits, warns, and rebalances without requiring the user to act as a human project manager.

## Non-Goals

- This PRD does not change the _packaging_ format of `.skill` files or the zip structure.
- This PRD does not introduce new tools or external dependencies.
- This PRD does not mandate a specific agent runtime (Claude, Kimi, Cursor); the limits must be portable across runtimes.
- This PRD does not retroactively resize existing plan files — guardrails apply to plans created after adoption.

## User Stories

- As a user running `aet-plan` or `aet-pipeline-plan`, I want every generated plan.md task to be session-sized so that I never again sit through a 3-hour agent session that degrades into incoherence.
- As a user reviewing `docs/plans/*.md`, I want oversized tasks to be automatically split with clear child dependencies so that I can approve a plan without manually decomposing it.
- As an agent executing from `aet-work`, I want the queue to contain only tasks I can finish in one go so that I don't need to ask "should I continue?" mid-task.

## Acceptance Criteria

- [ ] `aet-plan` `create-stories` enforces the guardrail: any story estimated > 2 human-days OR > 10 file changes OR > 500 lines of expected diff is auto-split into vertically-sliced child stories.
- [ ] `aet-plan` `plan` enforces the guardrail: any task in `plan.md` estimated > 4 agent-hours OR > 8 file changes OR > 300 lines of expected diff is auto-split into subtasks with explicit dependencies.
- [ ] `aet-pipeline-plan` passes the same guardrail at both story and plan stages without duplicating logic.
- [ ] `aet-work` `sync` validates incoming tasks against the guardrail and rejects (with a split suggestion) any task that violates it.
- [ ] `aet-implement` refuses to start a task whose `plan.md` contains `⚠️ ATOMIC OVERSIZED` without explicit `--force` flag or interactive user confirmation.
- [ ] The plan template (`.agents/templates/plan-template.md`) includes a "Task Size" field (S/M/L) with documented thresholds, and an explicit note that L tasks must be split.
- [ ] Every split operation produces a parent/child relationship documented in the plan (e.g., `Blocked by: parent-task-id` or `Split from: parent-task-id`).
- [ ] If auto-split fails (task is atomic and cannot be divided further), the agent emits a `⚠️ ATOMIC OVERSIZED` warning and requires explicit user acknowledgment before adding to the queue.

## Technical Notes

### Dual-Limit Model

| Layer                   | Human-Time Limit | AI-Complexity Limit            | When Checked     |
| ----------------------- | ---------------- | ------------------------------ | ---------------- |
| Story (PRD → ticket)    | ≤ 2 days         | ≤ 10 files OR ≤ 500 diff lines | `create-stories` |
| Task (ticket → plan.md) | ≤ 4 agent-hours  | ≤ 8 files OR ≤ 300 diff lines  | `plan`           |
| Queue entry             | Same as Task     | Same as Task                   | `aet-work sync`  |

- **Human-time** is an upper-bound sanity check to prevent "2-week refactoring" stories from entering the queue.
- **AI-complexity** is the operative limit because agent sessions fail on breadth (files touched) and depth (lines changed), not calendar time.
- A task fails if **either** limit is exceeded.

### Auto-Split Algorithm

1. Evaluate the task against both limits.
2. If within limits → accept.
3. If over limits → identify natural vertical slice boundaries:
   - By user-visible behavior (e.g., "user can register" vs "user can reset password")
   - By data entity (e.g., "user schema" vs "order schema")
   - By layer dependency (e.g., "backend API" before "frontend form")
4. Re-evaluate each child. Repeat until all children pass or max depth (3) is reached.
5. If max depth reached and a child still fails → mark `⚠️ ATOMIC OVERSIZED` and surface for user approval.

### Skill Changes Required

- `aet-plan/SKILL.md` — add guardrail rules to `create-stories` and `plan` command sections.
- `aet-pipeline-plan/SKILL.md` — reference the same guardrail; no duplicate logic.
- `aet-work/SKILL.md` — add `sync` validation step.
- `.agents/templates/plan-template.md` — add size field and split annotation format.
- `docs/CONVENTIONS.md` — document the dual-limit model as a toolkit-wide convention.

## Open Questions

1. ~~Should the limits be configurable per-project in `AGENTS.md`?~~ **Resolved: Hardcoded defaults for v1.** Configurable thresholds may be introduced later if teams with different context windows request them.
2. ~~Should `aet-implement` also enforce the guardrail at runtime?~~ **Resolved: Yes.** `aet-implement` must refuse to start a task whose `plan.md` contains an `ATOMIC OVERSIZED` marker without explicit user override (`--force` or interactive confirmation).
3. ~~Should split tasks share a common prefix in their IDs?~~ **Resolved: Yes, suffix convention `a`, `b`, `c`.** Example: `feat-auth-01` splits into `feat-auth-01a` and `feat-auth-01b`. This preserves lexicographic sort order and makes sibling relationships obvious at a glance.

## Revision Note

This PRD was superseded by `docs/prds/task-size-guardrails-revision-prd.md`. New plans created after the revision follow the context-budget + coherence model documented there. Existing approved plans remain valid and are not re-evaluated retroactively.

---

_Stage: prd-approved_
_Next step: run `aet-validate-scope`_

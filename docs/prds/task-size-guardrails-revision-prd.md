# PRD: Revise Task Size Guardrails for Agentic Planning

## Overview

The original Task Size Guardrails PRD (`docs/prds/task-size-guardrails-prd.md`) introduced a dual-limit model (human-time + AI-complexity) calibrated to keep agent sessions under roughly 100k tokens. Since then, context windows and runtime context management have improved; the 100k-token hard ceiling is less relevant, and the rigid proxies it produced — especially file-count and calendar-day limits — are causing over-fragmentation and artificial splits. This revision replaces those proxies with a context-budget + coherence rule, keeps the proven diff-line limits, and preserves the auto-split/`⚠️ ATOMIC OVERSIZED` safety net.

## Goals

- **G1:** Preserve the protective intent of the guardrail: no unbounded, multi-concern agent sessions enter the work queue.
- **G2:** Replace the 100k-token-fear rationale with context-budget and subsystem-coherence reasoning.
- **G3:** De-emphasize rigid file-count and calendar-time thresholds as primary limits while keeping human-time as a sanity check.
- **G4:** Keep diff-line limits as the operative complexity metric, with the validator's task-list-length check as their automatically enforced proxy.
- **G5:** Add explicit coherence checks (subsystems touched, architectural invariants) so that splits happen along subsystem boundaries and each fragment stays a coherent vertical slice. Retain the existing Batching Rule (`docs/CONVENTIONS.md`) as the guard against over-fragmentation.
- **G6:** Align the code validator (`src/aet/plan_parser.py`) with the documented model.
- **G7:** Do not retroactively invalidate existing approved plans.

## Non-Goals

- This PRD does not remove guardrails entirely.
- This PRD does not change the plan file format, frontmatter contract, or queue schema.
- This PRD does not introduce new tools, external dependencies, or project-specific runtime assumptions.
- This PRD does not re-evaluate existing merged/approved plans; the revised rules apply to plans created after adoption.

## Requirements

- **R-1:** The revised guardrail must prevent unbounded, multi-concern sessions from entering the queue.
- **R-2:** The revised guardrail must treat file count and calendar time as secondary signals, not hard primary limits.
- **R-3:** The revised guardrail must keep diff-line limits as the operative skill-level complexity metric, with the validator's task-list-length check documented honestly as its enforced proxy.
- **R-4:** The revised guardrail must add context-budget and subsystem-coherence guidance.
- **R-5:** The revised guardrail must preserve auto-split behavior and the `⚠️ ATOMIC OVERSIZED` override convention.
- **R-6:** The code validator must match the documented guardrail so intake does not contradict skill instructions.
- **R-7:** Existing approved plans must remain valid after the revision.
- **R-8:** The S/M/L size-label definitions must be redefined consistently with the revised model (no file-count trigger), and the plan frontmatter contract must remain valid.

## User Stories

- As a planner, I want guardrails that measure cognitive load rather than raw file count so that naturally broad but shallow changes are not artificially split (satisfies: R-2, R-4).
- As a reviewer, I want coherent vertical slices rather than arbitrarily tiny fragments so that each PR makes sense in isolation (satisfies: R-1, R-4).
- As an agent executing a plan, I want a clear context budget so I know when to checkpoint instead of guessing (satisfies: R-1, R-4).
- As a maintainer, I want the validator to match the documented guardrails so that `aet queue sync` and the skill instructions do not disagree (satisfies: R-6).

## Acceptance Criteria

- [ ] `skills/aet-plan/SKILL.md` replaces the dual-limit model with the context-budget + coherence model (satisfies: R-2, R-3, R-4).
- [ ] `docs/CONVENTIONS.md` Task Size Guardrails section is updated with the new model (satisfies: R-2, R-3, R-4).
- [ ] `.agents/templates/plan-template.md` references the revised limits and coherence checks (satisfies: R-2, R-3, R-4).
- [ ] `skills/aet-pipeline-plan/SKILL.md` references the revised guardrail without duplicating logic (satisfies: R-2).
- [ ] S/M/L label definitions in `docs/CONVENTIONS.md`, `.agents/templates/plan-template.md`, and `skills/aet-plan/SKILL.md` drop the file-count column, and L is redefined as a re-evaluation trigger rather than an automatic split trigger (satisfies: R-2, R-8).
- [ ] A full sweep updates the remaining references to the dual-limit model and the ≤ 8 files limit — including the `docs/CONVENTIONS.md` docs-taxonomy table and rules list, and the `create-stories` / `plan` command procedures in `skills/aet-plan/SKILL.md` (satisfies: R-2, R-6).
- [ ] `src/aet/plan_parser.py` `validate_size()` is updated to drop the file-count intake limit and keep the task-list-length limit; the now-unused `count_files_to_modify()` is removed (satisfies: R-2, R-3, R-6).
- [ ] `tests/queue/test_init_queue_sync.py` is updated to match the revised validator behavior, including a new test pinning that a plan listing more than 8 files but ≤ 300 task-list lines is accepted (satisfies: R-2, R-6).
- [ ] `docs/prds/task-size-guardrails-prd.md` carries a revision note linking to this PRD and explaining that new plans follow the revised model (satisfies: R-7).
- [ ] `make validate` passes after all changes (satisfies: R-5, R-6).

## Technical Notes

### Revised Guardrail Model

A plan/task is oversized when **any** of the following are true:

1. **Task-list length** (validator-enforced proxy for expected diff size):
   - Task: > 300 task-list lines, enforced by `validate_size()`. A task list that long is almost certainly a > 300-line diff; the docs must describe this metric as task-list length, not "diff lines."
2. **Story-level diff guidance** (skill-level only, **not** validator-enforced):
   - Story: > 500 expected diff lines.
3. **Human-time sanity check** (skill-level guidance, not validator-enforced):
   - Story: > 2 human-days.
   - Task: > 4 agent-hours.
4. **Subsystem coherence** (skill-level guidance):
   - Touches files in more than 2 distinct subsystems. A *subsystem* is a bounded module or layer with its own ownership boundary — in this repo, for example: `src/aet/` (CLI code + its tests), `skills/` (skill content), `.agents/` (workflow infrastructure), `docs/` (documentation). Edits spanning two of these (e.g., code and its tests) are one coherent change; three or more usually signal multiple concerns.
   - Requires maintaining more than one major architectural invariant at a time.
5. **Context budget** (skill-level guidance):
   - Loading the plan + all files to modify + relevant tests would exceed ~30k tokens for a task or ~50k tokens for a story.

The task-list-length check remains the only hard intake check. File count is no longer a rejection criterion; it is folded into the coherence and context-budget checks.

### Validator Change

`src/aet/plan_parser.py::validate_size()` currently rejects plans with `files > 8 or lines > 300`, where `lines` is the number of task-list lines (not expected diff lines). After this change it rejects only `lines > 300`. `count_files_to_modify()` has no other callers and is removed together with the file-count check. The `⚠️ ATOMIC OVERSIZED` marker remains the escape hatch for tasks that are genuinely atomic and exceed the limit. The unattended-mode hard stop on `⚠️ ATOMIC OVERSIZED` tasks and the `aet-implement` refusal behavior are unchanged.

### Size Labels

The S/M/L labels are retained — they are part of the plan frontmatter contract validated by `aet queue sync` — but their definitions drop the file-count column:

| Label | Human Time             | Expected Diff Lines |
| ----- | ---------------------- | ------------------- |
| S     | ≤ 2 hr                 | ≤ 100               |
| M     | ≤ 1 day                | ≤ 200               |
| L     | > 1 day OR > 200 lines | —                   |

**L is no longer an automatic split trigger.** An L task must be re-evaluated against the full model above and is split only if it actually exceeds a limit. This removes the contradiction where a coherent many-file change would be branded L and force-split under the old rule.

### Existing Plans

Existing `docs/plans/*.md` files are grandfathered. The validator change is forward-looking; existing approved plans with more than 8 files listed are not rejected on re-sync.

### Auto-Split and Atomic Oversized

The auto-split procedure and `⚠️ ATOMIC OVERSIZED` marker stay unchanged. Splits should now be guided primarily by:

- User-visible behavior boundaries
- Data entity boundaries
- Layer dependency boundaries
- Subsystem boundaries (new)

The existing Batching Rule in `docs/CONVENTIONS.md` is retained unchanged as the guard against over-fragmentation: near-identical, low-risk additions still get batched into a single plan rather than split per file.

## Open Questions

1. ~~Should the validator keep a high file-count backstop (e.g., 20 files) for pathological cases?~~ **Resolved: No.** Diff-line limit plus coherence guidance is sufficient; an arbitrary file backstop would reintroduce the same proxy problem.
2. ~~Should the context-budget guidance include a token-count heuristic?~~ **Resolved: Yes.** Use ~30k tokens for a task and ~50k tokens for a story as approximate planning guidance, with the caveat that actual model behavior varies.
3. ~~Should existing plans be re-evaluated under the new model?~~ **Resolved: No.** Existing approved plans are grandfathered; the revised model applies to plans created after adoption.

---

*Stage: scope-validated*
*Next step: run `aet-work` (single-plan or multi-task queue)*

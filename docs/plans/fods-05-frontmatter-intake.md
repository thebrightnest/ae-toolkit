---
id: fods-05-frontmatter-intake
blocked_by:
  - fods-02-state-spine
size: L
---

# Plan: Fail-Closed Intake on the Validated Frontmatter Contract

## Context

- PRD: `docs/prds/forward-only-deterministic-work-state-prd.md` (Workstream C, intake half)
- ADR: `docs/adr/011-forward-only-deterministic-work-state.md` (decision 4)

Intake fails open today: `plan_parser.py` scrapes a `## Blocked by` heading (only 8/86 plans use it) and derives `id` from the filename stem with no validation. This plan replaces that with a **validated YAML frontmatter contract** (`id`, `blocked_by`, `size`) and makes `sync`/`init-queue` **fail closed**. Intake also begins emitting the `fods-02` schema (`state`, `pending_blockers`, `history`).

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **Frontmatter parser + validation** — M (`aet-work/lib/plan_parser.py`)

   `parse_frontmatter(path) -> {id, blocked_by[], size}`. Validate: `id` present and equal to the filename stem; `size ∈ {S,M,L}`; `blocked_by` is a list of ids. Replace `blocked_by_from_plan` (heading scrape) and the `path.stem` id in `new_task_from_plan`. `new_task_from_plan` emits `state` (`ready` if `blocked_by` empty else `blocked`), `pending_blockers = len(blocked_by)`, and `history = [{from: null, to: "planned", by: "sync"}]`.

2. **Fail-closed `sync`** — M (`aet-work/bin/sync`)

   Reject (non-zero, naming the plan) any plan whose `id` is missing / duplicate / mismatched to its filename, whose `blocked_by` references an unknown id, or which is oversize without an explicit `⚠️ ATOMIC OVERSIZED` marker. Never emit a task with empty `blocked_by` caused by an unparsed section. Enforce **one plan = one task** (reject a multi-unit plan).

3. **Fail-closed `init-queue`** — S (`aet-work/bin/init-queue`)

   Apply the same validation via a shared helper so both intake paths fail closed identically.

4. **Update the plan template** — S (`.agents/templates/plan-template.md`)

   Adopt the frontmatter contract header; remove the `## Dependencies`/`## Blocked by` and `## Tasks`/`## Task List` divergence that caused the silent-drop failure.

5. **Tests** — M (`tests/test_init_queue_sync.py`, parser tests)

   - `test_valid_frontmatter_ingests_real_dag`
   - `test_reject_missing_or_mismatched_id`, `test_reject_duplicate_id`
   - `test_reject_unknown_blocker`, `test_reject_oversize_without_marker`
   - `test_emitted_task_has_state_pending_blockers_history`

6. **Merge branch to main and verify integration** — S

## Blocked by

- fods-02-state-spine

## Validation Steps

- [ ] A plan authored to the frontmatter contract ingests with a real `blocked_by` DAG.
- [ ] Each rejection path (missing/dup/mismatch id, unknown blocker, oversize) fails closed with a clear message.
- [ ] `sync` never emits a task with empty `blocked_by` due to an unparsed section.
- [ ] Emitted tasks carry `state`, `pending_blockers`, and an initial `history` entry.
- [ ] `.agents/templates/plan-template.md` uses the frontmatter contract.
- [ ] `make validate` passes.

## Rollback Plan

Revert `plan_parser.py`, `sync`, `init-queue`, and the template. Existing plans still parse under the prior heading-scrape path.

---

_Stage: qa-complete_
_Next step: run `aet-review`_

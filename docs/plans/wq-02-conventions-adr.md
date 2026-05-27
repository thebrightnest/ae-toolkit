# Plan: Conventions Update and ADR

## Context

PRD: `docs/prds/work-queue-atomicity-boundary-prd.md`

Document the directory convention for planning artifacts and create an ADR recording the structural boundary decision.

## Tasks

1. **Update `docs/CONVENTIONS.md`** — Add directory convention section — S

   - Add a new section under "Project Structure" or as a standalone section defining where each planning artifact type belongs
   - Reference the dual-limit model: only documents that pass the task-size guardrails may live in `docs/plans/`

2. **Create `docs/adr/006-work-queue-atomicity-boundary.md`** — Record the ADR — S

   - Context: The gap between planning and queue management
   - Decision: Directory separation (`docs/plans/` for atomic plans, `docs/roadmaps/` and `docs/audits/` for non-atomic)
   - Consequences: Positive (clean queue, 1:1 mapping), negative (requires user discipline to save docs in correct dirs)

3. **Run `make validate`** — Verify everything passes — S

## Dependencies

- Blocked by: `wq-01-skill-atomicity-updates` — the ADR should reference the actual skill changes

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] ADR follows the format in `docs/adr/000-template.md`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert `docs/CONVENTIONS.md` and delete the new ADR file.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_

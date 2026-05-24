# Plan: Document Task Size Conventions

## Context

- PRD: `docs/prds/task-size-guardrails-prd.md`
- The dual-limit model should be documented as a toolkit-wide convention so future skill authors follow it.

## Tasks

1. Update `docs/CONVENTIONS.md` — S

   - Add a "Task Size Guardrails" section
   - Document the dual-limit model (human-time + AI-complexity)
   - Document the S/M/L size mapping
   - Document the auto-split rule and max depth
   - Document the `ATOMIC OVERSIZED` marker convention

2. Run `make validate` — S

## Dependencies

- Blocked by `ts-01-aet-plan-guardrail` — the conventions should reference the actual skill behavior, not be speculative.

## Validation Steps

- [ ] `make validate` passes (markdownlint + format-check).
- [ ] Manual review: the new section is clear and complete.

## Rollback Plan

- Revert `docs/CONVENTIONS.md` from git.

---

_Stage: synced_
\_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`

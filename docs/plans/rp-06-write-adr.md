---
id: rp-06-write-adr
blocked_by:
  - rp-03-write-skill-core
size: S
---

# Plan: Write ADR for Ship/Release-Prep Separation

## Context

PRD: `docs/prds/aet-release-prep-prd.md`
AGENTS.md guardrail: "Always add an ADR in docs/adr/ for structural changes to the toolkit itself"

Document the decision to split release documentation from merge gating.

## Tasks

1. Read existing ADRs in `docs/adr/` to determine next sequence number
2. Write `docs/adr/00X-ship-release-prep-separation.md` covering:
   - Context: `aet-ship` previously implied changelog responsibility
   - Decision: Create `aet-release-prep` as a standalone skill for release docs
   - Consequences: `aet-ship` focuses on pre-merge gates; `aet-release-prep` focuses on changelog, PRODUCT.md, and version bump
   - Relationship: Release-prep runs after ship, when maintainers decide to cut a release
3. Merge branch to main and verify integration — S

**Estimated size:** S (≤ 2 hr, 1 file, ≤ 80 lines)

## Dependencies

- `rp-03-write-skill-core` (need to understand the final scope)

## Validation Steps

- [ ] ADR follows `docs/adr/000-template.md` format
- [ ] Sequential numbering is correct
- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git rm docs/adr/00X-ship-release-prep-separation.md` and commit.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_

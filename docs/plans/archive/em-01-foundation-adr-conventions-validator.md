---
id: em-01-foundation-adr-conventions-validator
blocked_by: []
size: S
---

# Plan: Execution Mode — Foundation (ADR, Conventions, Validator)

## Context

Links to PRD: `docs/prds/execution-mode-interaction-model-prd.md`

This plan establishes the architectural decision and conventions so that all future skills follow the same execution-mode pattern.

## Tasks

1. **Write ADR** — Document the execution-mode architectural decision in `docs/adr/005-execution-mode.md` — S
2. **Update CONVENTIONS.md** — Add an "Execution Mode" section to `docs/CONVENTIONS.md` describing the `AET_EXECUTION_MODE` contract, gate bypass protocol, and which gates must still stop in unattended mode — S
3. **Update skill-writing guide** — Add execution-mode guidance to `.agents/reference/skill-writing-guide.md` so new skill authors know how to handle interactive vs unattended contexts — S
4. **Add validator rule** — Update `scripts/validate-skills.sh` to flag any skill containing "Approve to proceed?" or "Hard gate" that does not also mention `AET_EXECUTION_MODE` — M
5. **Run validation** — `make validate` to ensure all changes pass lint and structure checks — S

## Dependencies

- None — this is the first plan in the sequence

## Validation Steps

- [ ] ADR follows `docs/adr/000-template.md` format
- [ ] CONVENTIONS.md section is clear enough for a new skill author to follow
- [ ] Validator script correctly flags skills missing execution-mode handling
- [ ] `make validate` passes
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. No application code is changed; only documentation and validation scripts.

---

_Stage: synced_
_Next step: run `aet-ship` to open a PR, then `post-ship-verify` to reach `merged`_

## Divergence Summary

**Scope additions beyond original plan:**

- Updated `aet-implement/SKILL.md` and `aet-pipeline-implement/SKILL.md` to use `AET_EXECUTION_MODE=unattended` (was in `em-03` plan, but required to satisfy the validator gate and ensure consistency).
- Updated `aet-work/SKILL.md`, `aet-work/references/context-isolation.md`, `aet-work/references/orchestrator-template.sh`, and `scripts/.aet-work-orchestrator.sh` to use `AET_EXECUTION_MODE=unattended` (was in `em-02` plan, but required to prevent mismatched signal naming).
- Updated `aet-setup/SKILL.md` to mention `AET_EXECUTION_MODE` in the generated AGENTS.md guardrails (so validator passes and generated projects inherit the convention).
- Regenerated all `.skill` packages via `make package`.

**Validator rule refinement:**

Original plan specified flagging skills with `"Approve to proceed?"` or `"Hard gate"`. Implemented rule flags only `"Approve to proceed?"` to avoid false positives on non-interactive hard-gate references (e.g., `aet-discover`'s "no code" gate, `aet-ship`'s merge-verification gate).

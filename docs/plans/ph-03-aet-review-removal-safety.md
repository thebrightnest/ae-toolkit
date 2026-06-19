---
id: ph-03-aet-review-removal-safety
blocked_by: []
size: M
---

# Plan: Add Removal Safety Lens to aet-review

## Context

During P3-REM cleanup, branch P3-REM-5 removed `selectSavePath` from the preload bridge, but `FlowsExportTab.tsx` still needed it. The retro calls for a "grep for removed preload methods in renderer" check. This plan adds a "Removal Safety" lens to `aet-review` that, when the diff deletes symbols from bridge/API files, greps the codebase for remaining references and flags them.

## Tasks

1. Update `aet-review/SKILL.md` — add "Removal Safety" to the review lens list (M)
2. Define the lens procedure: detect bridge/API file deletions, extract symbol names, grep tree, flag matches (M)
3. Create `aet-review/references/removal-safety-lens.md` if detail exceeds line budget (S)
4. Verify `make validate` passes (S)
5. Run `make package` to regenerate `.skill` files (S)

## Dependencies

- None — can start immediately

## Validation Steps

- [ ] `aet-review/SKILL.md` lists "Removal Safety" as a review lens
- [ ] The lens procedure is clear enough for an agent to execute without project-specific knowledge
- [ ] `aet-review/SKILL.md` remains under 400 lines
- [ ] `make validate` passes
- [ ] `make package` succeeds

## Rollback Plan

Restore `aet-review/SKILL.md` from git.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_

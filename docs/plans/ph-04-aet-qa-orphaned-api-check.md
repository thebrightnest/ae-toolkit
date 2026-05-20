# Plan: Add Orphaned API Call Check to aet-qa

## Context

The P3-REM retro found renderer files calling methods like `registryGet`, `getTrackedSessionBySessionId`, `listKnowledgeFiles` on `window.claudeApi` — but these methods had no real IPC handlers. They were dead code that only worked when the HTTP API layer was present. The retro calls for a check that "grep for `window.claudeApi` without a matching IPC handler should fail CI." Since the toolkit must remain agent-agnostic and project-agnostic, this plan adds a generic procedure to `aet-qa` for detecting orphaned API/bridge calls.

## Tasks

1. Update `aet-qa/SKILL.md` — add a "Call Completeness" validation step to the QA procedure (M)
2. Define the generic procedure: grep renderer for API call patterns, list them, require cross-reference with backend handlers (M)
3. Create `aet-qa/references/orphaned-api-check.md` if detail exceeds line budget (S)
4. Verify `make validate` passes (S)
5. Run `make package` to regenerate `.skill` files (S)

## Dependencies

- None — can start immediately

## Validation Steps

- [ ] `aet-qa/SKILL.md` documents a check for orphaned API/bridge calls
- [ ] The procedure is project-agnostic (no hardcoded `window.claudeApi` or similar)
- [ ] `aet-qa/SKILL.md` remains under 400 lines
- [ ] `make validate` passes
- [ ] `make package` succeeds

## Rollback Plan

Restore `aet-qa/SKILL.md` from git.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_

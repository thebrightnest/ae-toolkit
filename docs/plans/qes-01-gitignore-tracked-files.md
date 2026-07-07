---
id: qes-01-gitignore-tracked-files
size: S
blocked_by: []
pipeline: standard
---

# Plan: Gitignore Work Queue and Execution Log Files

## Context

Part of [PRD: Ephemeral Sprint Board for aet-work](../prds/aet-work-queue-ephemeral-sprint-board-prd.md). The work queue must stop being a tracked file so runtime sprint state no longer pollutes the working tree or blocks the orchestrator's hygiene check.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Add `.agents/work-queue.json` and `.agents/work-history.jsonl` to `.gitignore` — S
2. Remove the files from the git index without deleting local copies — S
3. Ensure `aet-work` commands recreate missing files on demand — S
4. Merge branch to main and verify integration — S

## Files to Modify

- `.gitignore`
- `aet-work/bin/init-queue` (ensure it creates the file if missing)
- `aet-work/bin/sync` (ensure it creates the file if missing)

## Validation Steps

- [ ] `git status --short` no longer lists `.agents/work-queue.json` or `.agents/work-history.jsonl` as tracked
- [ ] `make validate` passes
- [ ] `aet-work status` still works when the queue file is missing
- [ ] `git ls-files | grep -E 'work-queue|work-history'` returns nothing

## Rollback Plan

1. `git checkout -- .gitignore`
2. `git add .agents/work-queue.json .agents/work-history.jsonl`
3. Re-run `make validate`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_

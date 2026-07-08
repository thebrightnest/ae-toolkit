---
id: qes-08-state-auto-commit
size: S
pipeline: standard
status: ready
---

# Plan: Auto-commit plan closure updates in aet-state

## Context

`aet-state record-merge` (used by the `ship` closure helper) updates the plan file YAML frontmatter and footer to `merged`, but it leaves `main` dirty. A manual `chore(<task>): mark plan as merged after closure` commit is currently required after every merge.

## Task List

1. [x] Modify `aet-work/bin/aet-state` `cmd_record_merge` to stage and commit the plan file after `update_plan_status` — S
2. [ ] Run `make validate` — S
3. [ ] Ship and verify the fix closes itself cleanly — S

## Files to Modify

- `aet-work/bin/aet-state`

## Validation Steps

- [ ] `make validate` passes
- [ ] After `ship qes-08 ...`, `git status --short` on `main` is empty

## Rollback Plan

1. Revert the commit changing `aet-work/bin/aet-state`.
2. Re-run `make validate`.

---

_Stage: in-progress_
_Next step: run validation_

---
id: aet-ship-merge-default-main-plan
size: S
status: merged
blocked_by: []
pipeline: minimal
security_review: skipped
security_review_reason: trivial CLI default change, no new code paths
---

# Plan: Default aet ship merge --branch to main

## Context

Make `--branch` optional for `aet ship merge` so the common case of merging into
`main` does not require typing `--branch main`.

## Task List

1. Change argparse `--branch` from `required=True` to `default="main"`. — S
2. Change Typer `branch` option default from `...` to `"main"`. — S
3. Update `skills/aet-ship/SKILL.md` to note the default. — S
4. Update `tests/test_ship_merge.py` to expect default behavior. — S

## Files to Modify

- `src/aet/cli/ship.py`
- `skills/aet-ship/SKILL.md`
- `tests/test_ship_merge.py`

## Validation Steps

- [x] `aet ship merge <plan>` without `--branch` defaults to `main`.
- [x] Targeted ship tests pass.

## Rollback Plan

Revert the three file changes.

---

_Stage: merged_
_Next step: run `aet-work`_

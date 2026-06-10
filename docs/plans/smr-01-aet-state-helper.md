# Plan: Create aet-state Python Helper

## Context
PRD: `docs/prds/state-mechanization-review-independence-prd.md`

## Goal
Create scripts/aet-state.py — a standard-library Python helper that owns queue mutations, stage transitions, and footer updates.

## Tasks

### Task 1: Create scripts/aet-state.py
- [x] Implement `derive` command: recompute status from ground truth (git, filesystem)
- [x] Implement `transition` command: validate legality, then apply state change
- [x] Implement `validate` command: check if a proposed transition is legal
- [x] Implement `sync-footers` command: atomically update plan/PRD footers and queue JSON
- [x] Add `--dry-run` flag for safe testing

### Task 2: Define derivation rules
- [x] plan file exists → planned
- [x] branch exists → in-progress
- [x] git merge-base --is-ancestor → merged
- [x] worktree dir present → has worktree
- [x] JSON stores only DAG and abandoned + reason

### Task 3: Define legality rules
- [x] Cannot set merged without ancestry check
- [x] Cannot transition from abandoned without explicit reason clear
- [x] Cannot set done without merge verification (or explicit skip)

### Task 4: Add tests
- [x] Create test script that exercises each command
- [x] Test illegal transition rejection
- [x] Test derivation accuracy

## Validation
- [x] `python3 scripts/aet-state.py --help` works with no external dependencies
- [x] `derive` correctly computes status for a sample queue
- [x] `transition` rejects an illegal state change
- [x] `sync-footers` updates both plan footer and queue JSON atomically

## Rollback
Delete scripts/aet-state.py and test file.

---

*Stage: synced*
*Next step: run `aet-ship` to open a PR, then `post-ship-verify` to reach `merged`.*

# Plan: Create aet-state Python Helper

## Context

PRD: `docs/prds/state-mechanization-review-independence-prd.md`

## Goal

Create scripts/aet-state.py — a standard-library Python helper that owns queue mutations, stage transitions, and footer updates.

## Tasks

### Task 1: Create scripts/aet-state.py

- [ ] Implement `derive` command: recompute status from ground truth (git, filesystem)
- [ ] Implement `transition` command: validate legality, then apply state change
- [ ] Implement `validate` command: check if a proposed transition is legal
- [ ] Implement `sync-footers` command: atomically update plan/PRD footers and queue JSON
- [ ] Add `--dry-run` flag for safe testing

### Task 2: Define derivation rules

- [ ] plan file exists → planned
- [ ] branch exists → in-progress
- [ ] git merge-base --is-ancestor → merged
- [ ] worktree dir present → has worktree
- [ ] JSON stores only DAG and abandoned + reason

### Task 3: Define legality rules

- [ ] Cannot set merged without ancestry check
- [ ] Cannot transition from abandoned without explicit reason clear
- [ ] Cannot set done without merge verification (or explicit skip)

### Task 4: Add tests

- [ ] Create test script that exercises each command
- [ ] Test illegal transition rejection
- [ ] Test derivation accuracy

## Validation

- [ ] `python3 scripts/aet-state.py --help` works with no external dependencies
- [ ] `derive` correctly computes status for a sample queue
- [ ] `transition` rejects an illegal state change
- [ ] `sync-footers` updates both plan footer and queue JSON atomically

## Rollback

Delete scripts/aet-state.py and test file.

---

_Stage: plan-approved_
_Work class: critical_
_Next step: aet-pipeline-implement_

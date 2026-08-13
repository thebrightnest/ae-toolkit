---
id: owb-08-single-source-ledger-path
size: S
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
docs_sync: required
---

# Plan: One Derivation for Where the Ledger Lives

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirement: R-12
- Precedent: ADR-023 solved this for verdict paths

Four call sites derive the ledger four ways, and `cli/gate.py:368` resolves differently by launch mode because only the batch path sets `AET_REPO_ROOT`. `ship.py:860`'s bare `Ledger()` is CWD-relative.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. **Add the exported resolver**, mirroring `evidence.resolve_verdict_path`'s contract — S (traces: R-12)
2. **Convert all five writers** — `sprint.py:149`, `aet_state.py:584`, `aet_state.py:735`, `gate.py:369`, `ship.py:860` — S (traces: R-12)
3. **Pin agreement in tests** from inside a worktree, with `AET_REPO_ROOT` set and unset — S (traces: R-12)
4. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: independent of the board work, and a real split-brain today.
- [x] Diff exceeds overhead: one resolver, five call sites, a launch-mode matrix.
- [ ] Could share a branch with `owb-07` — kept separate because one is provenance and one is the board.

## Rejected Alternatives

- **Fix `ship.py` only** — rejected: the launch-mode split at `gate.py` is the one that misled a downstream session.
- **Normalise by always setting `AET_REPO_ROOT`** — rejected: that variable carries two meanings; leaning on it entrenches the collision.

## Files to Modify

- `src/aet/ledger.py`
- `src/aet/cli/gate.py`, `aet_state.py`, `sprint.py`, `ship.py`
- `tests/ledger/`

## Validation Steps

- [ ] Every writer resolves the same store from inside a worktree under both launch modes
- [ ] No call site constructs `Ledger()` without the resolver
- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert. The resolver returns today's location for the default configuration, so no ledger moves.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/owb-08-single-source-ledger-path.md*

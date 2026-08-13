---
id: owb-12-config-honesty
size: M
work_class: normal
blocked_by:
  - owb-11-shadow-posture
pipeline: standard
security_review: required
docs_sync: required
---

# Plan: A Setting That Cannot Take Effect Is an Error

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirements: R-20, R-23

`_validate_options` (`cli/configure_backend.py:169`) checks the *values* of two options; nothing checks for unknown keys, so `projection` instead of `projections` is silently ignored. Two contradictions already exist: `configure`'s help says the default backend is git-refs while `factory.py:62` defaults to json, and `setup verify` prints built-in defaults as project config under a venv install.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. **Reject unknown and misspelled keys**, naming the legal ones — M (traces: R-20)
2. **Refuse contradictory combinations**, including shadow posture alongside a `projections` entry or a project-scope config file — M (traces: R-20)
3. **Report provenance** for every effective value, using the existing `resolve_config_with_source` — S (traces: R-20)
4. **Fix the documented-vs-actual default** disagreement — S (traces: R-20)
5. **Add an explicit shared-across-devices switch** to `aet configure`, and document that an unconfigured project is local — M (traces: R-23)
6. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: config honesty is valuable independently of any phase.
- [x] Diff exceeds overhead: a key schema, a conflict matrix, a provenance pass, a new option.
- [x] Cannot precede `owb-11`, which defines the posture the conflicts are about.

## Rejected Alternatives

- **Warn instead of failing on unknown keys** — rejected: a warning that changes nothing is the silence this PRD removes.
- **Infer the shared-device intent from a remote's presence** — rejected: it re-creates the guessing that R-23 replaces with a stated choice.

## Files to Modify

- `src/aet/cli/configure_backend.py`
- `src/aet/backends/factory.py`
- `src/aet/cli/setup.py`
- `docs/CONVENTIONS.md`
- `tests/backends/`, `tests/installer/`

## Validation Steps

- [ ] A misspelled key fails with the legal keys named
- [ ] Shadow plus a projection entry fails with the contradiction stated
- [ ] `setup verify` reports the source layer of each value
- [ ] One command declares a project shared across devices
- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert. Configuration files are unchanged; only their validation is.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/owb-12-config-honesty.md*

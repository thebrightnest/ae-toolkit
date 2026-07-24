---
id: epi-11-branch-model-docs-and-verify
size: S
blocked_by: [epi-01-base-branch-resolver, fic-02-installer-bootstrap-boundary]
pipeline: standard
status: queued
security_review: skipped
security_review_reason: displays an already-resolved value and edits documentation; no new input or write surface
docs_sync: required
docs_sync_reason: this plan is the documentation deliverable (R-23) plus the setup verify display (R-5)
---

# Plan: Document the branch model and surface the resolved trunk

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-5, R-23)
- ADR: `docs/adr/044-base-branch-is-configured-not-assumed.md` (risk: silent
  fallback to `main`)

R-5 was deferred out of `epi-01`: `aet setup verify` does not exist yet — it is
created by `fic-02-installer-bootstrap-boundary` under the fresh-install PRD.
This plan carries that cross-PRD blocker so the resolver is never stalled on
unrelated installer work. The resolver already returns provenance (`epi-01`);
this plan is display plus documentation, which is why it is S.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Locked design

- **The resolved trunk is inspectable, not inferred.** `aet setup verify`
  prints the resolved trunk branch and how it was derived — `config`,
  `detected` (from `refs/remotes/origin/HEAD`), or `fallback` (to `main`). The
  silent-fallback risk ADR-044 names is acceptable only because this output
  exists; on a repo with an unset symbolic-ref and a non-`main` trunk, the
  operator sees `fallback: main` instead of discovering it via a failed run.
- **Documentation states the model once, in the config section it extends.**
  `docs/CONVENTIONS.md` already has the "AET Backend Configuration" section
  with the external-first resolution order; the branch model belongs there,
  not in a new document. It covers: what `trunk_branch`,
  `integration_branch`, and `integration_mode` mean; their resolution orders;
  and a worked Scenario B setup (one engineer, shared repo, plans on a feature
  branch, `single-pr`).
- **No behavior changes.** The display reads the resolver; the docs describe
  what `epi-01` through `epi-10` built. If implementation and this text
  disagree, the text loses and is corrected in the `docs_sync` gate.

## Task List

1. Print the resolved trunk and its provenance in `aet setup verify`
   — S (traces: R-5)
2. Document the branch model, resolution orders, and a worked Scenario B setup
   in `docs/CONVENTIONS.md` — M (traces: R-23)
3. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — one display, one doc
      section
- [ ] The diff is expected to exceed 3 files or 50 lines — it does not; batched
      anyway because both deliverables are "make the branch model visible" and
      share one review
- [x] Cannot share a branch with `epi-07` — docs of a moving target rot; this
      lands after the config surface exists

## Rejected Alternatives

- **Ship R-5 inside `epi-01`** — rejected there: `aet setup verify` does not
  exist, and blocking the resolver on `fic-02` would stall everything
  downstream for installer work from another PRD.
- **A standalone `docs/branching.md`** — rejected: the config section in
  `docs/CONVENTIONS.md` is where an operator already looks for resolution
  order; a second document splits the answer.
- **Detect and warn on a stale `refs/remotes/origin/HEAD`** — rejected: the
  symbolic-ref cannot be distinguished from a deliberate one without asking the
  remote, and verify is a local inspection. Displaying provenance is the
  honest version of the same signal.

## Files to Modify

- `src/aet/cli/setup.py`
- `docs/CONVENTIONS.md`
- `tests/setup/test_verify_reports_trunk.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] New source coverage: `tests/setup/test_verify_reports_trunk.py` asserts
      verify prints the resolved trunk and its provenance on a repo with an
      unset `refs/remotes/origin/HEAD` (shows `fallback: main`), a detected
      `dev` trunk, and a config-set trunk (PRD acceptance criterion, R-5)
- [ ] `docs/CONVENTIONS.md` states the resolution order for all three settings
      and contains the worked Scenario B setup (PRD acceptance criterion, R-23)
- [ ] R-trace coverage: R-5 by task 1; R-23 by task 2
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Verify stops printing the branch line and the doc section
disappears; no code path depends on either.

## Pipeline

`standard`.

---

*Stage: reviewed*
*Next step: run `aet-sync-docs`*

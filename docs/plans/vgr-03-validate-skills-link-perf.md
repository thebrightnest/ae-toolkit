---
id: vgr-03-validate-skills-link-perf
size: M
blocked_by: []
pipeline: standard
status: draft
security_review: skipped
security_review_reason: Internal refactor of a local link-resolution loop in a bash validator; identical inputs/outputs, no network, no new trust boundary.
docs_sync: skipped
docs_sync_reason: Internal script optimization with unchanged observable behavior; no documented contract changes.
---

# Plan: De-Subshell `validate-skills.sh` Link Check (+ Its First Test)

## Context

PRD: [validate-gate-review](../prds/validate-gate-review-prd.md). Satisfies **R-5**
(link validation runs materially faster with identical results, covered by a named
test).

`scripts/validate-skills.sh` costs 22.78s — the second-largest gate. The hot spot
is the relative-link check (~lines 162–185): per markdown file it strips code
blocks with `sed`, then for **each link** spawns several subshells (`echo | sed`,
case matches) inside a `while read` loop. Across 454 files that is thousands of
process spawns. The script currently has **no test**, so a test is added first to
lock behavior before the refactor.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (performance), not a defect

## Task List

1. Add `tests/test_validate_skills.py` — drive `scripts/validate-skills.sh` via `subprocess` against temp fixtures: a skill dir with a valid relative link (exit 0), one with a broken relative link (nonzero exit, message names the file/link), and one exercising the code-block/`http`/anchor skips. Captures current behavior as the baseline. — M (traces: R-5)
2. Refactor the relative-link check (~lines 162–185) to eliminate per-link subshells: a single pass (awk, or one inline `python3 -c`) that resolves each link once while preserving code-block stripping and the `http`/anchor skips. — M (traces: R-5)
3. Verify (see Validation Steps) and merge — S (traces: R-5)

**Size labels:** 2 files, ~110 diff lines (new test ~80 + refactor ~30) → **M**.

## Batching Check

- [x] Not near-identical additions
- [x] Diff > 50 lines
- [x] Independent file (`scripts/validate-skills.sh`); cannot batch with the Makefile/docs plans

## Rejected Alternatives

- **Rewrite `validate-skills.sh` entirely in Python** — rejected: far larger blast radius (frontmatter, dirs, trigger-uniqueness, next-step checks) for a link-loop problem; out of scope.
- **Accept the 22.78s** — rejected: it is the second-largest gate cost and the owner chose to optimize it.

## Files to Modify

- `scripts/validate-skills.sh`
- `tests/test_validate_skills.py` (new)

## Validation Steps

- [ ] Lint passes (ruff on the new test; `make validate` green)
- [ ] `tests/test_validate_skills.py` passes against **both** the original and refactored script (baseline preserved)
- [ ] `validate-skills.sh` wall time on the full repo is materially reduced (record before/after)
- [ ] **New source file** `tests/test_validate_skills.py` — an integration test (pytest drives the bash script via subprocess) covering the link-validation behavior of `scripts/validate-skills.sh`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

**Self-consistency lint:** Check 1 PASS · Check 2 (script=t2, test=t1) PASS · Check 3 (observable: exit codes + timing) PASS · Check 4 (R-5 covered) PASS.

## Rollback Plan

`git revert` the refactor commit; the test remains green on the original script (baseline captured), so it stays as net-new coverage.

## Pipeline

`standard` — code change with a new test; default grouping.

---

_Stage: plan-approved_
_Next step: run `aet-work`_

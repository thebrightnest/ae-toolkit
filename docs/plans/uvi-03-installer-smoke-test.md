---
id: uvi-03-installer-smoke-test
size: M
status: queued
blocked_by:
  - uvi-02-curl-installer-script
pipeline: standard
security_review: skipped
security_review_reason: Test runs only in temporary directories and exercises the same installer code reviewed in uvi-02.
docs_sync: skipped
docs_sync_reason: No documentation change beyond the test itself.
---

# Plan: Add smoke test for the curl installer

## Context

Part of the [uv one-line installer PRD](../prds/uv-one-line-installer-prd.md) (`docs/prds/uv-one-line-installer-prd.md`). A hermetic, offline smoke test exercises `scripts/install.sh` in isolated temporary directories (cloning from the local checkout via `--repo`) so onboarding regressions are caught before merge.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create a pytest test or shell test harness that sets a temporary `HOME`, `AET_BIN_DIR`, and `AET_SKILLS_DIR` — S (traces: R-13)
2. Run `scripts/install.sh --repo <local-checkout> --bin-dir <tmp> --skills-dir <tmp>/skills --agent generic` from the test, with no network access — M (traces: R-13)
3. Assert `aet --version` exits 0 from the temp bin dir — S (traces: R-13)
4. Assert at least one skill symlink resolves (`<tmp>/skills/aet-setup/SKILL.md`) — S (traces: R-13)
5. Assert the installer is idempotent by running it a second time — S (traces: R-10)
6. Add a `--dry-run` assertion that no files are created — S (traces: R-2)
7. Wire the test into `make validate` or a standalone `test-installer` Make target — S (traces: R-13)

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Batching Check

- [x] This is not one of several near-identical additions
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] The work cannot share a branch/PR with related tasks (this is the verification task)

## Rejected Alternatives

- **Manual QA only** — rejected: onboarding is the first impression; it needs automated regression coverage.
- **Test against real `~/.local/bin` and `~/.claude/skills`** — rejected: mutates the developer's machine; tests must use temp directories.

## Files to Modify

- `tests/cli/test_installer_smoke.py` — new pytest test
- `Makefile` — add `test-installer` target and optionally wire into `validate`

## Validation Steps

- [ ] Test passes locally: `make test-installer`
- [ ] Test passes via `make validate` from a clean checkout (this repo has no CI; all gates are local)
- [ ] Test cleans up temporary directories even on failure
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task; no task cites an unknown R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the test commit; the installer script remains but lacks automated coverage until the test is restored.

---

_Stage: qa-complete_
_Next step: run `aet-review`_

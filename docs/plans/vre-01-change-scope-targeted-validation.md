---
id: vre-01-change-scope-targeted-validation
size: M
blocked_by: []
pipeline: standard
status: queued
security_review: skipped
security_review_reason: changes which tests `make validate` selects locally; no new input, auth, data, or write surface, and the fail-toward-full-suite default bounds the blast radius of any mapping gap
docs_sync: required
docs_sync_reason: ADR-049 and the change_scope mapping table must agree; CONVENTIONS/PIPELINE references to the prose-only skip need the tiered/targeted contract
---

# Plan: change_scope Emits Code-Derived Targeted Validation Scope

## Context

- PRD: `docs/prds/validation-runtime-efficiency-prd.md` (R-1, R-2, R-3)
- ADR: `docs/adr/049-validation-scope-from-change-set.md` (this plan delivers it)
- Measured motivation: `reports/2026-07-24-validation-runtime-review.md` — `make validate`
  runs the whole ~1,200-test suite for any code change and runs `test-installer` on every
  invocation.
- Verified current contract (2026-07-24): `change_scope.decide()` returns `FULL`/`DOCS` and
  `main()` prints `"tests/"` or `""` (`src/aet/change_scope.py:92-118`); the Makefile
  consumes that stdout as `PYTEST_TARGETS` (`Makefile:106-108`) and then runs
  `test-installer` unconditionally (`Makefile:112`). `change_scope.is_code_path` already
  delegates to `evidence.default_is_code_path` (`change_scope.py:37`), and
  `evidence.validation_freshness` already defines a `RUN`/`LINT_ONLY`/`SKIP` tier
  (`src/aet/evidence.py:232-324`).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `change_scope` maps the changed-file set to a **minimal pytest target list** via a small,
  explicit path-prefix → test-dir table, printed on stdout. `make validate` consumes it
  unchanged via `PYTEST_TARGETS` — **no Makefile plumbing change** for R-1.
- The installer smoke test becomes an entry in that mapping: `change_scope` emits
  `tests/installer/test_installer.py` only when `scripts/install.sh` or `src/aet/cli/setup.py`
  is in the change set. The unconditional `test-installer` line (`Makefile:112`) is removed —
  the *only* Makefile edit, a deletion, with the installer decision now living in Python.
- The scope **tier** is computed from the change set reusing `evidence`'s
  `RUN`/`LINT_ONLY`/`SKIP` vocabulary — never keyed on the plan's `*Stage:*` label.
- **Fail toward more tests:** `conftest.py`, shared fixtures, unmapped paths, or an
  undetermined diff fall back to the full suite. A wrong skip hides a regression; a wrong
  include costs one run.

## Rejected Alternatives

- **Keep the binary `"tests/"`/skip contract** — rejected: it is the measured source of the
  redundant full-suite + unconditional-installer cost; the target-list plumbing already
  exists (ADR-049).
- **A discrete installer flag the Makefile reads with an `if`** — rejected in favor of
  folding the installer test into the same target-list mapping, so all decision logic stays
  in `change_scope` Python and the Makefile only loses a line (ADR-049 decision 2).
- **A `change_scope`-local code/non-code classifier** — rejected: extend the shared
  `evidence.default_is_code_path` primitive, do not fork it (ADR-049).

## Task List

1. Map changed files → minimal pytest target list in `change_scope.decide()/main()`, with the
   fail-toward-full-suite fallback for `conftest.py`/shared/unmapped/undetermined — M
   (traces: R-1)
2. Fold the installer smoke test into the mapping (emit `tests/installer/...` only when the
   installer surface changed) and delete the unconditional `test-installer` line in the
   `validate` target — S (traces: R-2)
3. Compute the scope tier from the change set reusing `evidence`'s `RUN`/`LINT_ONLY`/`SKIP`
   vocabulary; assert it never reads the plan stage — S (traces: R-3)
4. Tests (see Validation Steps) — S (traces: R-1, R-2, R-3)
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: `change_scope` is the single scope authority; R-1/R-2/R-3 all extend one
  file's stdout contract and share one test file — one coherent, independently shippable unit.

## Files to Modify

- `src/aet/change_scope.py`
- `tests/test_change_scope.py`
- `Makefile` (delete the unconditional `test-installer` line in `validate`; no plumbing change)
- `docs/CONVENTIONS.md` (document the mapping table + fail-toward-full-suite rule)

## Validation Steps

- [ ] `make validate` passes
- [ ] Coverage:
  - `test_change_scope_maps_source_dir_to_targeted_test_dir` (unit)
  - `test_change_scope_falls_back_to_full_suite_on_conftest_or_shared_fixture` (unit)
  - `test_change_scope_emits_installer_target_only_when_installer_surface_changed` (unit)
  - `test_change_scope_omits_installer_target_for_unrelated_change` (unit)
  - `test_change_scope_tier_reuses_evidence_vocabulary_and_ignores_stage` (unit)
- [ ] R-trace coverage: R-1 by tasks 1, 4; R-2 by tasks 2, 4; R-3 by tasks 3, 4; no unknown R-ids
- [ ] For the new mapping logic in `change_scope.py`, tests above name the coverage
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; `change_scope` returns to the binary `"tests/"`/skip contract and the
Makefile's unconditional installer line is restored — the Makefile `PYTEST_TARGETS` plumbing is
unchanged either way, so the revert is self-contained.

---

*Stage: plan-approved*

*Next step: run `aet run-one docs/plans/vre-01-change-scope-targeted-validation.md`*

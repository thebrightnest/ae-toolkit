---
id: cfg-03-cli-surface-fixes
size: S
blocked_by: []
pipeline: minimal
status: queued
security_review: skipped
security_review_reason: forwards a flag the orchestrator already accepts and sanitizes, and displays already-resolved values; no new input or write surface
docs_sync: required
docs_sync_reason: CLI help and CONVENTIONS.md must agree on the forwarded --base flag and the new verify output
---

# Plan: CLI Surface Fixes — Forward `--base`, Show Resolved Mode

## Context

- PRD: `docs/prds/aet-config-file-overhaul-prd.md` (R-6, R-7)
- Verified consumer breakage (2026-07-24): `aet run --base feat/x` fails —
  `--base` exists only on the orchestrator's internal Typer CLI
  (`src/aet/cli/orchestrator.py:3090-3094`) and the dispatcher
  (`src/aet/cli/main.py:280-334`) does not expose it. CONVENTIONS.md also
  documents it under the wrong name (`--base-branch`); the doc-side fix is
  cfg-05, this plan makes the real flag reachable.
- `aet setup verify` (`src/aet/cli/setup.py:279-310`) currently prints only
  the resolved trunk (epi-11); users cannot confirm `single-pr` before a run.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `aet run` and `aet run-one` accept `--base <branch>` and forward it to the
  orchestrator exactly as the internal CLI does today; precedence stays
  `--base` → `AET_WORK_BASE_BRANCH` → config → trunk (ADR-044, unchanged).
- `aet setup verify` prints resolved `integration_mode`,
  `integration_branch`, and `trunk_branch`, each with provenance
  (`config (project|user|env)` / `detected` / `fallback` / `default`),
  extending epi-11's trunk display. Read-only; no new resolution logic beyond
  surfacing what the resolvers already return.

## Rejected Alternatives

- **Dropping `--base` from docs instead of forwarding it** — rejected: the
  per-run override is the ADR-044-sanctioned way to point a run at an epic
  branch; removing it would force per-epic config edits.
- **A new `aet config show` command instead of extending `setup verify`** —
  rejected: `setup verify` already exists for exactly this inspectability
  (epi-11); a second surface splits the diagnostic story.

## Task List

1. Accept and forward `--base` in the `aet run` / `aet run-one` dispatcher —
   S (traces: R-6)
2. Print resolved `integration_mode` / `integration_branch` / `trunk_branch`
   with provenance in `aet setup verify` — S (traces: R-7)
3. Tests (see Validation Steps) — S (traces: R-6, R-7)
4. Merge branch to main and verify integration — S [Deferred: ship stage]

**Size definitions:** S ≤ 2 hr / ≤ 150 lines.

### Floor Check

- [x] Stands alone: pure bug-fix/discoverability surface; shippable
  independently of the config overhaul.

## Files to Modify

- `src/aet/cli/main.py`
- `src/aet/cli/setup.py`
- `tests/cli/test_run_dispatcher.py` (new or extend existing dispatcher tests)
- `tests/cli/test_setup_verify.py` (new or extend existing)

## Validation Steps

- [ ] `make validate` passes
- [ ] Coverage:
  - `test_run_forwards_base_to_orchestrator` (unit)
  - `test_run_one_forwards_base_to_orchestrator` (unit)
  - `test_setup_verify_prints_mode_and_branches_with_provenance` (unit)
  - `test_setup_verify_marks_fallback_provenance` (unit)
- [ ] R-trace coverage: R-6 by tasks 1, 3; R-7 by tasks 2, 3; no unknown R-ids
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; the orchestrator's internal `--base` and the old
verify output are unaffected by the revert.

---

_Stage: plan-approved_
_Next step: run `aet-work`_

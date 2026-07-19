---
id: pkg-13-scripts-split
size: S
blocked_by:
  - pkg-03-lib-extraction
pipeline: minimal
status: approved
security_review: skipped
security_review_reason: Repo-hygiene reorganization of maintenance scripts; no runtime or dependency changes.
docs_sync: required
docs_sync_reason: AGENTS.md directory structure and CONVENTIONS.md must describe the new scripts/ split.
---

# Plan: Split `scripts/` by Audience (A5)

## Context

PRD: [aet-package-extraction](../prds/aet-package-extraction-prd.md) (R-10).
`scripts/` mixes repo-maintenance tooling (`validate-skills.sh`,
`skills-lint`, `test-*.sh`) with one-off data migrations
(`migrate-plans-to-frontmatter.py`, `migrate-telemetry-slugs.py`) and stray
`test-*.py` files. Split by audience and decide the migrations' fate.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Inventory `scripts/`; classify each as maintenance (stays), migration
   (archive), or misplaced test (move to `tests/`) — S (traces: R-10)
2. Move `scripts/test-aet-state.py` and `scripts/test-telemetry.py` into
   `tests/` as proper pytest modules (or delete if fully duplicated by
   existing tests — verify first) — S (traces: R-10)
3. Archive the one-off migrations to `scripts/archive/` with a README noting
   the release they shipped in; decide `aet migrate` vs. archive (default:
   archive — the migrations have already run; record if reversed) — S
   (traces: R-10)
4. Update `AGENTS.md` and `docs/CONVENTIONS.md` directory descriptions and
   any `Makefile` references — S (traces: R-10)
5. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] Small hygiene plan; batching with pkg-07 was considered and rejected
  (tests/ vs scripts/ are different audiences).

## Rejected Alternatives

- **`aet migrate` subcommand** — rejected as default: both migrations are
  one-offs already applied to this repo's state; packaging them adds a CLI
  surface with no future caller. Archive preserves them for reference.
- **Delete the migrations outright** — rejected: they document a real data
  transition; cheap to keep archived.

## Files to Modify

- `scripts/test-aet-state.py`, `scripts/test-telemetry.py` → `tests/`
- `scripts/migrate-*.py` → `scripts/archive/`
- `scripts/archive/README.md` (new)
- `AGENTS.md`, `docs/CONVENTIONS.md`, `Makefile` (references)

## Validation Steps

- [ ] `make validate` green; relocated test modules run under pytest
- [ ] `scripts/` contains only maintenance tooling referenced by `Makefile` or
  docs; every remaining file has a named caller
- [ ] No references to moved paths remain (`grep -rn "scripts/test-\|scripts/migrate-" Makefile docs/ .agents/`)
- [ ] R-trace coverage: R-10 by tasks 1–4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert`; moves only.

---

*Stage: plan-approved*
*Next step: run `aet-work`*

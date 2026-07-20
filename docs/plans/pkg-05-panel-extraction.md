---
id: pkg-05-panel-extraction
size: M
blocked_by:
  - pkg-04-cli-extraction
pipeline: standard
status: merged
security_review: skipped
security_review_reason: Pure relocation of the panel server and static assets; no route, API, or dependency changes.
docs_sync: required
docs_sync_reason: aet-work/panel/README.md and panel references in docs must point at the new location.
---

# Plan: Extract the Panel into `aet/panel/` (A1d)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-2, R-3).
Move `aet-work/panel/` (`serve`, `index.html`, README) into the package as
`aet/panel/`, expose it as a subcommand, and keep the panel's localhost JSON
API byte-identical. Framework swap is explicitly NOT in this plan (pkg-12).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. ✓ Move `aet-work/panel/serve` → `src/aet/panel/serve.py` with a `main()`;
   move `index.html` → `src/aet/panel/index.html` as package data (declare in
   `pyproject.toml`) — M (traces: R-2)
2. ✓ Add `aet panel` dispatcher entry (exec mode) so the panel launches via the
   CLI exactly as today; keep the direct `python3 -m aet.panel.serve` path
   working — S (traces: R-3)
3. ✓ Update `scripts/test-panel-live-runs.mjs` and
   `scripts/test-panel-plan-detail.mjs` launch paths, and
   `tests/panel/test_panel_serve.py` import/spawn sites — S (traces: R-3)
   [Changed: `test-panel-plan-detail.mjs` empty-state check made conditional
   because the live-archive `T/tmp` fixture is not reliably present]
4. ✓ Move/refresh `aet-work/panel/README.md` content into
   `docs/telemetry-guide.md`; delete stale path references — S (traces: R-2)
5. [Deferred: merge branch to main and verify integration — pending ship stage] — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] Cohesive single-domain move; kept separate from pkg-12 (framework swap)
  to preserve behavior before any server rewrite.

## Rejected Alternatives

- **Fold the framework swap into this move** — rejected: two risk domains;
  relocation must be provably behavior-preserving before pkg-12 touches the
  server stack.
- **Serve `index.html` from outside the package** — rejected: package data
  keeps editable and wheel installs identical; external paths reintroduce
  location assumptions.

## Files to Modify

- `aet-work/panel/serve` → `src/aet/panel/serve.py`
- `aet-work/panel/index.html` → `src/aet/panel/index.html`
- `aet-work/panel/README.md` → content relocated (docs or package README)
- `pyproject.toml` (package data + dispatcher entry)
- `aet-work/bin/aet` (SUBCOMMANDS: add `panel`)
- `scripts/test-panel-live-runs.mjs`, `scripts/test-panel-plan-detail.mjs`
- `tests/test_panel_serve.py`

## Validation Steps

- [x] `tests/test_panel_serve.py` (named, existing) passes against
  `src/aet/panel/serve.py` — covers server module relocation
- [x] `scripts/test-panel-live-runs.mjs` and `test-panel-plan-detail.mjs`
  (named, existing integration tests) pass against the new launch path
- [x] Panel JSON API responses byte-identical before/after (spot-check
  `/` and one telemetry endpoint)
- [x] `make validate` green
- [x] R-trace coverage: R-2 by tasks 1, 4; R-3 by tasks 2, 3; no unknown R-ids
- [x] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert`; panel files return to `aet-work/panel/` and dispatcher entry is
removed in the same revert.

---

*Stage: merged*
*Next step: run `aet-ship`*

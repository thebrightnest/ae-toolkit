---
id: lvp-01-panel-live-run-visibility
size: M
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: modifies the panel's localhost HTTP handler to walk the telemetry archive and emit a new dirs payload — verify archive-root confinement and no path-traversal regression on the new code path
docs_sync: required
docs_sync_reason: panel README status section and stale worktree-dev note must reflect main-tree development + live-run support; docs/telemetry-guide.md review path gains live-run behavior
---

# Plan: Panel Live-Run Visibility (dirs API + honest status)

## Context

PRD: `docs/prds/panel-live-executions-prd.md`. First of two plans (lvp-02
adds auto-refresh). Today a run is invisible until its first stage record
lands and any run without `last-run.json` is mislabeled `success`. Verified
live 2026-07-13: run `b0cfc5a5` ran 20+ min with an empty run dir and
returned zero `/api/list` entries. The parser already tolerates
`summary == null` runs with records (`aet-work/panel/index.html:191-201`);
this plan adds dir visibility, the live/incomplete status model, and the
rendering. No orchestrator changes.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. `serve`: add a run-dir walk to `telemetry_files()`'s sibling logic —
   collect every current-layout run dir (`{project}/{YYYY-MM-DD}/{run-id}`,
   parent basename parses as a date, mirroring `telemetry.py:_iter_project_run_dirs`)
   with `mtime` = newest recursive mtime (dir + files, same definition as
   `telemetry.py:_newest_mtime`); return them as `dirs: [{rel, mtime}]` in
   the `/api/list` JSON alongside the unchanged `files` array — S (traces: R-1) ✅
2. `tests/test_panel_serve.py` (new): load `aet-work/panel/serve` via
   importlib against a tmp fixture archive (empty run dir, dir with partial
   JSONL, stale dir, completed dir, legacy `{date}-{run-id}` dir) — assert
   `dirs` includes the empty dir, excludes the legacy dir, `mtime` equals
   the newest file's mtime after an append, `files` is byte-identical to
   today, and `/api/file` still 404s on `..` traversal — S (traces: R-1) ✅
3. Panel data plumbing (`index.html`): thread `dirs` from
   `loadTelemetryFromApi` through `collectGroups`/`buildRunsFromGroups`:
   create a zero-record run entry for every dir with no file group, and
   attach each dir's `mtime` to its run as `lastActivity` (fallback for
   folder-picker mode, where `dirs` is absent: latest record end time) —
   M (traces: R-1, R-2) ✅
4. Status model (`index.html`): add `LIVE_FRESHNESS_MINUTES = 30`; for runs
   with no summary, status = `live` when `now - lastActivity < 30 min`,
   else `incomplete` (summary runs keep the existing outcome logic; a
   no-summary run never renders `success`/`failure`); Runs table sort key
   becomes `live` first, then `lastActivity` descending — S (traces: R-2) ✅
5. UI rendering (`index.html`): `live` badge (pulsing emerald dot; keyframe
   in the existing `<style>` block) and `incomplete` badge (amber) in the
   Runs table; add both to the status filter options; run-detail banner for
   no-summary runs ("In progress — N stage records, last activity Xm ago";
   zero-record dirs: "Waiting for first stage record"); live dot on plan
   rows in the Plans lens when any contributing run is `live`; the pulse
   keyframe gets a `prefers-reduced-motion` fallback that renders the dot
   static — M (traces: R-2, R-3) ✅
6. `scripts/test-panel-live-runs.mjs` (new): CDP E2E on the
   `test-panel-plan-detail.mjs` pattern (zero npm deps), spawning `serve`
   with `HOME=<tmp fixture>` — assert: empty-dir run row renders with
   `live` badge; stale no-summary dir renders `incomplete`; live row sorts
   first; run detail shows the banner; Plans lens shows the live dot; zero
   console errors — M (traces: R-2, R-3) ✅
7. Docs (`aet-work/panel/README.md`): status section gains live-run
   support; replace the stale "Where panel development lives" section with
   main-tree development (the aet-panel worktree was temporary, confirmed
   by owner 2026-07-13); note live features are served-mode only — S
   (traces: R-2, R-3) ✅
8. Merge branch to main and verify integration — S _(deferred to the ship
   stage; qa/review/cso gates run first in this pipeline)_

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks (lvp-02 depends on this plan's API + status model).

## Rejected Alternatives

- **Lease-file / PID cross-check for liveness** — rejected: the lease lives
  in each project repo, outside the archive the serve process is scoped to;
  mtime signals are archive-native and shared with prune safety.
- **Plain dir mtime instead of newest-recursive** — rejected: JSONL appends
  bump the file's mtime, not the dir's; a run mid-second-stage would look
  stale while actively writing.
- **Per-file mtimes in the API** — rejected: larger payload, and the panel
  only needs one activity timestamp per run; newest-recursive per dir is
  the same aggregate prune already trusts.
- **Including legacy `{date}-{run-id}` dirs in `dirs`** — rejected: every
  legacy dir contains files (they predate this feature), so the panel
  already sees them; zero added signal.
- **Single combined plan with lvp-02** — rejected: ~470 estimated diff
  lines trips the L split rule; and "visible on load" is a valuable,
  independently shippable slice.

## Files to Modify

- `aet-work/panel/serve`
- `aet-work/panel/index.html`
- `aet-work/panel/README.md`
- `tests/test_panel_serve.py` (new)
- `scripts/test-panel-live-runs.mjs` (new)

## Validation Steps

- [x] `make validate` green (lint, format, ruff, pytest, skill-structure validator)
- [x] `tests/test_panel_serve.py` passes — unit/API-boundary coverage of the
      `dirs` payload contract (serve ↔ panel), including traversal-guard
      regression and append-updates-mtime
- [x] `node scripts/test-panel-live-runs.mjs` passes — E2E/integration
      coverage of live/incomplete rendering against a fixture archive
      (real serve + headless Chrome), zero console errors
- [x] Manual smoke: with a real `aet run` in flight, the run's row appears
      on panel load with a `live` badge before any stage completes —
      verified in parts 2026-07-13: fixture E2E covers the empty-dir → live
      badge render path; real-archive API smoke shows the in-flight run
      `17e9ccc4` in `dirs` with accurate activity age (mid-stage quiet
      window >30 min renders `incomplete`, the PRD-accepted behavior lvp-02
      polling recovers)
- [x] R-trace coverage: R-1 (tasks 1–3), R-2 (tasks 3–6), R-3 (tasks 5–7)
      covered; no task cites an R-id outside the PRD
- [x] New source files have named tests: `tests/test_panel_serve.py` covers
      the serve change; `scripts/test-panel-live-runs.mjs` covers the panel
      rendering change
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`
      _(ship stage)_

## Rollback Plan

Revert the merge commit. `dirs` is additive to `/api/list`, so an older
panel ignores it; reverting the panel alone restores prior behavior against
a new serve. No archive data is touched by this plan.

## Pipeline

`pipeline: standard` — modifies an HTTP handler and a security-relevant
filesystem walk; the aet-cso gate (`security_review: required`) must verify
archive-root confinement on the new dirs listing.

---

_Stage: implemented_
_Next step: run `aet-qa`_

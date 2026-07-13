---
id: lvp-02-panel-auto-refresh
size: M
blocked_by:
  - lvp-01-panel-live-run-visibility
pipeline: minimal
security_review: skipped
security_review_reason: client-side polling of the existing /api/list endpoint inside the panel; no server/endpoint changes, no new network surface, React auto-escaping throughout (same boundary as thp-05/06)
docs_sync: skipped
docs_sync_reason: panel README status section updated within the plan; no docs/ tree impact beyond what lvp-01 already synced
---

# Plan: Panel Auto-Refresh (polling + poll-diff liveness)

## Context

PRD: `docs/prds/panel-live-executions-prd.md`. Second of two plans, blocked
by lvp-01 (which ships the `dirs` API, the live/incomplete status model,
and the rendering this plan keeps fresh). Today the panel loads the archive
once and only reloads on the manual **Refresh archive** button, so a live
run's progress is stale seconds after the page opens. This plan adds
visibility-gated polling with incremental re-fetch, and upgrades liveness
detection with the poll-diff signal: a run whose archive mtime advances
between polls is `live` regardless of age (covers stages that run longer
than the 30-minute freshness window).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Poll loop (`index.html`): after the initial load, `setInterval` 5s while
   `document.visibilityState === "visible"` AND at least one no-summary run
   dir has `lastActivity` younger than 60 minutes; each tick fetches
   `/api/list` with `cache: "no-store"`; pause on `visibilitychange` to
   hidden, resume (with an immediate tick) on visible — S (traces: R-4)
2. Incremental merge (`index.html`): diff the polled `dirs` against the
   previous snapshot by `(rel, mtime)`; for new dirs and dirs whose mtime
   advanced, re-fetch only that dir's files via `/api/file`, rebuild those
   runs through the lvp-01 plumbing, and merge into the run list in place —
   preserving the active lens, filters, and selected run/plan; unchanged
   dirs are never re-fetched — M (traces: R-4)
3. Poll-diff liveness (`index.html`): track each dir's last-seen mtime; a
   no-summary run whose mtime advanced since the previous poll is `live`
   regardless of the 30-minute freshness window from lvp-01 (a run past the
   window with no mtime change stays `incomplete`) — S (traces: R-2, R-4)
4. Extend `scripts/test-panel-live-runs.mjs`: against the fixture archive,
   append a stage record to a live dir mid-session and assert the Runs
   table row gains the record within ~6s without a manual refresh; assert a
   run older than the freshness window whose mtime advances flips
   `incomplete → live`; assert no polling occurs while the tab reports
   hidden (CDP `Emulation.setFocusEmulationEnabled` or visibility override)
   — M (traces: R-4)
5. Docs (`aet-work/panel/README.md`): status section notes auto-refresh
   behavior, the 5s cadence, the 60-minute polling window, and poll-diff
   liveness — S (traces: R-4)
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks (blocked by lvp-01; separate PR per repo convention).

## Rejected Alternatives

- **SSE / WebSocket streaming** — rejected: `/api/list` is a cheap localhost
  directory walk (3,090 files at the 2026-07-11 peak, ~140 today);
  long-lived connections add server complexity for no perceptible gain
  (panel README reached the same conclusion for log tailing).
- **Full archive reload on every poll** — rejected: at peak archive size
  (3,090 files) a 5s full reload is wasteful and churns React state
  (filters, selection, scroll); the dir-mtime diff limits fetches to
  changed run dirs only.
- **Unconditional polling (no activity window)** — rejected: a panel left
  open overnight would wake every 5s forever; the 60-minute
  no-summary-activity window stops polling once runs settle, and manual
  Refresh always remains available.
- **mtime-age-only liveness (no poll-diff)** — rejected: a healthy 45-minute
  stage writes nothing until completion and would sit mislabeled
  `incomplete`; the poll-diff signal recovers `live` the moment any record
  lands.

## Files to Modify

- `aet-work/panel/index.html`
- `aet-work/panel/README.md`
- `scripts/test-panel-live-runs.mjs`

## Validation Steps

- [ ] `make validate` green (lint, format, ruff, pytest, skill-structure validator)
- [ ] `node scripts/test-panel-live-runs.mjs` passes — E2E/integration
      coverage: mid-session append reflected ≤ ~6s without manual refresh,
      `incomplete → live` on mtime advance, no polling while hidden, zero
      console errors
- [ ] Regression: `tests/test_panel_serve.py` still passes (no serve
      changes in this plan)
- [ ] Manual smoke: panel open during a real `aet run` shows stage records
      appearing without touching Refresh; closing the laptop lid (tab
      hidden) pauses polling
- [ ] R-trace coverage: R-4 (tasks 1–5) covered; R-2 refinement (task 3)
      cites an in-scope PRD R-id; no unknown R-ids
- [ ] No new source files introduced (extends lvp-01's named E2E harness)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Polling is purely additive client-side behavior;
the lvp-01 panel continues to work with manual Refresh only. No archive or
API changes in this plan.

## Pipeline

`pipeline: minimal` — all stages in one session. Chosen 2026-07-13 (owner
decision): this plan is pure client-side polling of an existing endpoint —
no auth, data-model, API-surface, or dependency changes — and lvp-01 showed
the multi-session overhead dominating wall-clock (~90 min for a 635-line
diff, most of it per-session ramp-up and repeated full-suite runs). The CSO
gate stays deliberately skipped (no new network surface).

---

_Stage: plan-approved_ (owner approval + closure check 2026-07-13)
_Next step: run `aet-work`_

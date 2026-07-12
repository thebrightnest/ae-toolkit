---
id: thp-06-panel-plan-detail
size: M
blocked_by:
  - thp-05-panel-plans-lens
pipeline: standard
status: approved
security_review: skipped
security_review_reason: client-side React rendering of local telemetry inside the existing panel; no server/endpoint changes, no new network surface, React auto-escaping throughout
docs_sync: skipped
docs_sync_reason: panel README status/roadmap updated within the plan; no docs/ tree impact beyond what thp-05 already synced
---

# Plan: Panel Plan Detail — Spine, Consolidated Timeline, Run Chips

## Context

- PRD: `docs/prds/telemetry-hygiene-plan-panel-prd.md` (R-6). Approved design: panel README "Plan-centric consolidated view" — the plan is the unit of intent; a run is the execution vehicle; a plan's lifecycle spans queue re-runs, retries, resumes.
- Builds directly on thp-05's plan model (`buildPlans`, `normalizePlanFile`, `worktreeOf`, `taskPlanMap`, lens state) — `blocked_by` thp-05, same `index.html`.
- **Precondition P-0** inherited via thp-05: panel v1 on `origin/main` before queueing.
- Known multi-run fixture in the live archive for verification: wfd-01/wfd-02 plans span the 2026-07-06 → 2026-07-11 runs, including the 09:03–10:03 run.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

Replace thp-05's basic plan card with full `PlanDetail`:

- **Header**: plan name, project, overall status badge, contributing-run count.
- **Pipeline spine**: the six states from `aet-work/workflows/software.json` (`plan-approved → implemented → qa-complete → reviewed → secure → synced`) rendered as a horizontal stepper; per state: done (a success stage record names it in `stage`/`stages`), failed (latest record naming it failed), pending (no record) — shows where the plan stalled.
- **Consolidated timeline**: one chronological table of every stage session **and** test run for the plan across **all** runs (start_time asc). Columns: Time | Run (shortId chip) | Worktree (`worktreeOf` from thp-05) | Kind (stage/test) | Stage | Duration | Result. Retries appear as repeated rows — this is the "all runs combined" view.
- **Aggregates**: environment issues and learning candidates across all the plan's runs, reusing the existing `RunDetail` section tables/components.
- **Run chips**: chip row of contributing runs; click → `setLens("runs")` + select that run's dir (existing `selectedId` mechanism) — the cross-lens link.
- Reuse existing components (`Table`, `Badge`, `ResultBadge`, `SectionTitle`, `fmtDuration`, `fmtTime`, `shortId`) — no new styling primitives.
- **Empty states** (UI-lens finding): a plan attributed only via `run_summary.task_ids` can have zero timeline rows — render the existing "no rows" table pattern ("No stage sessions or test runs recorded for this plan") instead of an empty table; spine states all-pending is valid and renders as such.
- Scope note (decided): the view starts at `plan-approved`; earlier human-driven steps (aet-plan, PRD, validate) emit no telemetry and get no placeholder states.

## Rejected Alternatives

- **Per-run sub-grouping inside the timeline** — rejected: the approved design is one chronological stream with run id as a column/chip; grouping by run re-creates the run-centric view the plan lens replaces.
- **Rendering unreached spine states from plan frontmatter (e.g. skipped gates)** — rejected: telemetry doesn't carry gate-routing keys; inferring them from absence would show wrong "skipped" states. Pending is honest.
- **Linking timeline rows to session logs** — rejected: session-log capture is deferred (PRD non-goal); nothing to link yet.

## Task List

1. `PlanDetail` component: header + pipeline spine per Locked design — M (traces: R-6)
2. Consolidated timeline table + aggregated issues/learnings sections — M (traces: R-6)
3. Run chips with cross-lens navigation into existing run detail — S (traces: R-6)
4. Update `aet-work/panel/README.md` (status: plan-centric view shipped; roadmap tick) — S (traces: R-6)
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Renderer / UI Tasks

- [ ] `PlanDetail`, spine stepper, timeline styled with existing Tailwind utilities over the shadcn tokens — no new custom CSS
- [ ] Verify no unstyled `className` references remain (console clean under Tailwind Play)

### Batching Check

- [x] Not a near-identical addition
- [x] Diff ~220 lines / 2 files
- [x] Cannot share a branch with thp-05: sequential edits to the same single-file app; combined diff would exceed M

## Files to Modify

- `aet-work/panel/index.html`
- `aet-work/panel/README.md`

## Validation Steps

E2E against the live archive (no JS unit harness — accepted, matches panel verification method):

- [ ] `python3 aet-work/panel/serve --no-open` + headless-Chrome E2E (named steps): (1) select the wfd-01 plan → spine shows its completed states and stall point; (2) timeline contains rows from ≥ 2 distinct run ids, chronologically ordered, with worktree + duration + result populated; (3) a retried stage appears as repeated rows; (4) clicking a run chip lands on that run's detail in the Runs lens; (5) aggregated issues/learnings match the sums of the contributing runs; (6) zero console errors
- [ ] Runs lens regression: run detail unchanged for a spot-checked run
- [ ] `make validate` green
- [ ] R-trace coverage: R-6 by tasks 1–4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — Plans lens falls back to thp-05's basic plan card; Runs lens unaffected.

---

_Stage: implemented_
_Next step: run `aet-qa`_

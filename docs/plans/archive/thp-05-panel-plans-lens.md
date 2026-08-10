---
id: thp-05-panel-plans-lens
size: M
blocked_by: []
pipeline: standard
status: merged
security_review: skipped
security_review_reason: client-side React rendering of local telemetry inside the existing panel; no server/endpoint changes, no new network surface, React auto-escaping throughout
docs_sync: required
docs_sync_reason: telemetry guide's "Reviewing a single run" section gains the panel (plans-lens) as the primary review path
---

# Plan: Panel Plans Lens — Plan Model, Tabs, Plan List

## Context

- PRD: `docs/prds/telemetry-hygiene-plan-panel-prd.md` (R-5). Approved design: panel README "Plan-centric consolidated view" + "Terminology & information architecture".
- **Precondition P-0 (hard)**: panel v1 must be on `origin/main` before this plan is queued — today `aet-work/panel/` exists only as uncommitted files in `.worktrees/aet-panel`, and task worktrees are cut from `origin/main`. Do not `aet-work add` this plan until P-0 is done.
- Everything is buildable from existing records (verified): `stage`/`test_run`/`environment_issue`/`learning_candidate` carry `plan_file`; `run_summary` carries `task_ids`. No `serve` or orchestrator changes.
- Panel is a single self-contained `index.html` (718 lines, React 18 UMD + Babel standalone + Tailwind Play CDN, no build step). Run model: `buildRunsFromGroups`/`buildRun`; grouping memos at :612-615; UI is `App` + `RunsTable` + `RunDetail`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **Normalization** — `normalizePlanFile(p)`: slice from `"docs/plans/"` when present (raw values look like `{REPO_ROOT}/.worktrees/<task>/docs/plans/<plan>.md`); else fall back to basename; plan display name = basename without `.md`. Without this, the same plan run from main vs a worktree splits in two.
- **Worktree attribution** — `worktreeOf(rawPlanFile)`: match `/\.worktrees\/([^/]+)\//` → capture, else `"main"` (stored per record for thp-06's timeline column).
- **Join** — global `taskPlanMap` (task_id → normalized plan) built from every record carrying both fields (verified 1:1 today; on conflict keep first, count in meta). `run_summary`-only runs attribute to plans via `task_ids` through the map.
- **Plan model** — `buildPlans(runs)`: group records by (project, normalized plan); per plan: sessions (stage records), tests, issues, learnings, contributing run refs, `lastActivity` (max end_time/timestamp), spine progress = set of completed state names from `stage`/`stages` fields on success records, intersected with the spine constant `["plan-approved","implemented","qa-complete","reviewed","secure","synced"]` (from `aet-work/workflows/software.json`), status = failure if the chronologically last session/test failed.
- **UI** — `lens` state (`"plans"` default | `"runs"`), two-button shadcn-style tab strip in the header row; Plans lens reuses the master-detail grid: `PlansTable` (columns: Plan | Project | Runs | Sessions | Tests | Progress n/6 | Last activity | Status) + a **basic** plan card on the right (name, project, run count, aggregate stats — full detail is thp-06). Existing folder/project/status/search filters apply to both lenses (plan search over plan name, project, task ids). Runs lens = today's UI unchanged.
- Terminology (decided): top-level = **Project**, rows = **Plans**; "folder" label retired from the UI copy where it means project.

## Rejected Alternatives

- **Shipping list + full detail in one plan** — rejected: single-file diff would blow past M (~400 lines); vertical split = "see plans" (this) then "drill into a plan" (thp-06).
- **Emitting a plan-id field from the orchestrator instead of normalizing paths** — rejected: panel-side normalization needs no telemetry changes and works for all existing records; stable frontmatter ids are a PRD non-goal (v1).
- **Blocking this plan on thp-02 (slug redesign)** — rejected: grouping consumes whatever two-segment slug exists; no functional dependency (verified `index.html:612-615` logic is shape-generic).

## Task List

1. Data layer in `index.html`: `normalizePlanFile`, `worktreeOf`, `taskPlanMap`, `buildPlans` wired after run parsing — M (traces: R-5) [x]
2. Lens tabs + `PlansTable` + basic plan card, filters applied per lens, Plans as default; Runs tab byte-identical behavior — M (traces: R-5) [x]
3. Update `aet-work/panel/README.md`: status + roadmap tick, and fix the glossary conflict found at scope validation — the README calls the telemetry archive "the execution log", but CONTEXT.md reserves **Execution Log** for `.agents/work-history.jsonl`; reword to **telemetry archive** — S (traces: R-5) [x]
4. Merge branch to main and verify integration — S (deferred: merge happens at the ship/merge stage, after review)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Renderer / UI Tasks

- [x] New components (`Tabs` strip, `PlansTable`, plan card) styled with existing Tailwind utility classes over the shadcn zinc tokens — no custom `className` values requiring new CSS
- [x] Verify no unstyled `className` references remain (Tailwind Play CDN resolves utilities at runtime; check console for warnings)

### Batching Check

- [x] Not a near-identical addition
- [x] Diff ~200 lines / 2 files
- [x] Cannot share a branch with thp-06 (it builds on this plan's model and would exceed M combined)

## Files to Modify

- `aet-work/panel/index.html`
- `aet-work/panel/README.md`

## Validation Steps

No JS unit harness exists (no build step — accepted); validation is E2E against the live archive, mirroring the panel's existing verification method:

- [x] `python3 aet-work/panel/serve --no-open` starts; `curl -s localhost:<port>/api/list` returns 200 with files (server untouched — regression check)
- [x] Headless-Chrome E2E (named steps): (1) panel auto-loads and opens on **Plans** lens with ≥ 1 plan row for this repo's project; (2) a plan that ran from a task worktree and from main shows as **one** row (normalization); (3) a `run_summary`-only run's plan appears (task_ids join); (4) Runs tab reproduces today's table + run detail; (5) zero console errors
- [x] `make validate` green
- [x] R-trace coverage: R-5 by tasks 1–3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` (deferred to ship/merge stage)

## Rollback Plan

Revert the merge commit — `index.html` returns to the runs-only panel; no data or server surface changed.

---

_Stage: merged_
_Next step: run `aet-ship`_

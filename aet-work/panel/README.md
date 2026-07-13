# AET Telemetry Panel

Browser-based viewer for the aet-work telemetry archive (`~/.aet/telemetry`).

## Usage

```bash
python3 aet-work/panel/serve   # serves panel + archive on 127.0.0.1, opens your browser
```

- `--no-open` — serve without opening a browser (prints the URL).
- Fallback: open `index.html` directly and pick the telemetry folder manually
  (the page tells you to use the launcher instead).
- The launcher is localhost-only, stdlib-only, refuses path traversal, and
  ignores `work-history.jsonl` (queue-history copies, not execution records).
  API: `GET /api/list` (returns `files` plus `dirs` — run dirs with activity
  mtimes), `GET /api/file?p=<relpath>`.

## Design

- **No build step.** `index.html` is self-contained: React 18 + ReactDOM UMD,
  Babel standalone (pinned `@7.26.2` — `@latest` is a broken Babel 8
  prerelease), Tailwind Play CDN (pinned `3.4.17`).
- **shadcn** has no CDN distribution, so its component recipes (Card, Button,
  Badge, Select, Table) are recreated with Tailwind classes over the shadcn
  zinc theme tokens (CSS variables in `<style>`).
- Everything runs client-side; nothing leaves the machine.

## Status (as of 2026-07-13)

Working and verified:

- Auto-loads `~/.aet/telemetry` on open; **Refresh archive** button; archive
  path shown in the header.
- Live-run visibility (lvp-01, **served mode only** — the folder picker has no
  dir listing): `/api/list` additionally returns `dirs`, every current-layout
  run dir with its newest recursive mtime (same definition prune safety
  trusts), so a just-started run with an empty dir appears on load. Runs
  without `last-run.json` get an honest status: **live** (pulsing emerald
  dot, activity fresher than `LIVE_FRESHNESS_MINUTES` = 30) or **incomplete**
  (amber) — never a fake success. The Runs table sorts live first, then last
  activity; run detail shows an in-progress banner ("Waiting for first stage
  record" for zero-record dirs, "In progress — N stage records, last activity
  Xm ago" otherwise); plan rows get a live dot when any contributing run is
  live; the status filter gains Live/Incomplete options; the pulse honors
  `prefers-reduced-motion`. Verified: `tests/test_panel_serve.py` (API
  contract) and `scripts/test-panel-live-runs.mjs` (fixture archive +
  headless Chrome, zero console errors).
- Two lenses via a tab strip in the header: **Plans** (default) and **Runs**.
  - Plans lens groups records by normalized plan file (paths into
    `.worktrees/<task>/` are sliced to `docs/plans/<plan>.md`, so a plan run
    from a worktree and from main is one row), attributes `run_summary`-only
    runs through a global task→plan map, and shows runs, sessions, tests,
    pipeline progress (n/6 on the `software.json` spine), last activity, and
    status per plan. Selecting a plan opens the full plan detail (thp-06):
    header with contributing-run count, a six-state **pipeline spine**
    stepper (done/failed/pending per state, latest record wins — the stall
    point is the first non-done state), a **consolidated timeline** of every
    stage session and test run across all of the plan's runs (chronological;
    retries appear as repeated rows; run-summary-only plans get a "no rows"
    empty state), aggregated environment issues / learning candidates, and
    **run chips** linking into the Runs lens.
  - Runs lens is the original runs table + run detail, unchanged.
- Stat cards: runs/plans, stage sessions, success rate, total time (per lens);
  run detail also shows **Tokens** and **Cost** cards (uct-01).
- Filters: **folder** (top-level archive subfolder) → **project** (scoped to
  the folder) → status → free-text search (task, plan, run id); they apply to
  both lenses.
- Master-detail: runs table + run detail with Stages, Test runs, Environment
  issues, and Learning candidates sections (schema:
  `aet-work/references/telemetry-log-schema.md`).
- Usage & cost view (uct-01, 2026-07-12): Tokens + Cost columns on the runs
  table, per-stage rows (run detail Stages table, plan timeline), and
  Tokens/Cost stat cards in run detail. Run aggregates prefer the
  summary's `total_tokens`/`total_cost_usd`, falling back to summing stage
  records; `null` (pre-uct-01 records, unsupported CLIs, or subscription
  aliases without a per-token price) renders as `—` so old archives look
  intentional, not broken.
- Format tolerance: nested project slugs (`demo/project/...`), run dirs
  without `last-run.json`, legacy `{project}/{date}-{run-id}/execution.log.jsonl`
  layout (split into one run per `run_summary` record), corrupted legacy lines
  skipped and counted in the header.
- Verified: headless-Chrome E2E (auto-load on the Plans lens, plan-row counts
  matching an independent archive scan for `thebrightnest/ae-toolkit` and
  `aiskills/main`, `run_summary` join, plan card, Runs tab regression, zero
  console errors); `make validate` green.
- Plan detail verified 2026-07-12 (thp-06): repeatable headless-Chrome E2E
  harness (`scripts/test-panel-plan-detail.mjs`, zero npm deps, CDP over
  Node's built-in WebSocket) against the live archive — wfd-01 spine states +
  stall point, 4-row timeline across 2 runs matching an independent archive
  scan, retried `reviewed` stage as repeated rows, run-chip cross-lens
  navigation, aggregate counts, empty state for `run_summary`-only plans,
  zero console errors; `make validate` green.

## Known quirks

- The `tests`, `demo/project`, `tmp*`, and `T/tmp*` "projects" are **pytest
  pollution**, not real projects: the test suite spawns the real orchestrator
  ~160 times per run, and only 4 of those spawns set
  `AET_TELEMETRY_ARCHIVE_DIR`, so the rest write into the real archive. Slug
  shapes come from `derive_project_slug()` (`aet-work/lib/telemetry.py:65`):
  explicit `AET_PROJECT_ID` (`tests`, `demo/project`), temp-dir fallback
  (`tmp*`), or origin = temp path (`T/tmp*`). The slug scheme itself is being
  redesigned — see "Project slug redesign" below.
- A 1-week retention cleanup ran on 2026-07-11 (removed 103 dated run dirs
  older than 2026-07-04 + 2,897 empty leftover dirs; 30 MB → 23 MB). The
  prune snippet is documented in `docs/telemetry-guide.md` ("Privacy and
  retention"). June-era legacy archives were removed by that rule. The same
  cleanup also deleted the **active** run dir of a live `aet run`
  (wfd-03): the run's bookkeeping crashed and the task DAG stalled even
  though every worktree commit was intact (learning recorded in
  `.agents/learnings.jsonl`). Rule going forward: never prune the active run —
  check `.agents/work-queue.lease` for the live run id before deleting.

## Where panel development lives

- Panel work happens in the **main tree** on ordinary feature branches
  branched from `origin/main`, like any other toolkit change. The dedicated
  `aet-panel` worktree was a temporary arrangement while main-tree panel
  edits were restricted; the owner confirmed on 2026-07-13 it is no longer
  needed.
- The orchestrator stash quirk still applies to uncommitted main-tree files:
  a running aet-work orchestrator stashes them at run start ("aet-work-run:
  temp stash") and pops them back when the run finishes (observed 2026-07-11).
  Commit panel work before launching a run from the main tree.

## Findings & decisions (2026-07-11)

### Why "aiskills" never appeared in the panel

- Telemetry derives the project slug from the git **origin remote**, not the
  local directory: `derive_project_slug()` (`aet-work/lib/telemetry.py:65`)
  takes the last two parts of the origin URL. This repo's origin is
  `github.com:thebrightnest/ae-toolkit`, so every run launched here is filed
  under folder `thebrightnest` → project `thebrightnest/ae-toolkit`. The
  local dir name (`aiskills`) is only the fallback when there is no origin.
- Verified end to end against the live panel API: folder list
  `[T, demo, tests, thebrightnest]`; `thebrightnest/ae-toolkit` holds this
  project's runs for 2026-07-06 → 2026-07-11 (including the 09:03–10:03 run
  with tasks `wfd-01-*` / `wfd-02-*`). Nothing was broken — the project was
  listed under a name the owner didn't recognize.

### Project slug redesign (decided, not implemented)

- **New rule:** slug = `<main-worktree-dir>/<current-worktree-dir>`, e.g.
  `aiskills/main`, `aiskills/wfd-03-engine-rewiring`, `aiskills/aet-panel`.
  Detect with `basename(dirname(git rev-parse --git-common-dir))` +
  `basename(git rev-parse --show-toplevel)`; label the primary worktree
  `main`. Keep the `AET_PROJECT_ID` override (escape hatch, and the way to
  merge two clones into one project). Non-git fallback stays the bare dir
  name.
- **Why local-path identity is safe here:** the panel is a local,
  single-machine tool, so cross-machine stability and folder-rename survival
  don't matter. Per-worktree grouping is a feature: folder = which repo,
  project = which worktree. The one failure mode — a run's stage sessions
  scattering across per-task worktree "projects" — cannot happen, because
  the orchestrator pins `AET_REPO_ROOT` into every spawned session's env
  (`aet-work/bin/orchestrator:1176`) and `resolve_repo_root()` honors it
  before asking git (`aet-work/lib/telemetry.py:46`). Identity is the
  orchestrator's launch root, always.
- **Accepted trade-offs:** two separate clones of the same repo → two
  projects; two unrelated repos sharing a directory name in different
  parents → merged; moving or renaming folders starts fresh (out of scope by
  decision).
- **Migration:** records don't embed the slug, so it's pure directory
  renames — `thebrightnest/ae-toolkit` → `aiskills/main`,
  `thebrightnest/artifactsh` → `artifactsh/main`. `aet report` follows
  automatically (it shares the function).
- **Blast radius:** `derive_project_slug()` (`aet-work/lib/telemetry.py:65`)
  - docs. Panel grouping logic (`index.html:612-615`) needs no change — the
    two-segment slug shape is preserved.

### Terminology & information architecture (decided)

- **Project** — the repo (top level; previously mislabeled "folder").
- **Run** — one orchestrator invocation (the table rows; not "projects").
- **Worktree** — where a run was launched; an attribute/filter of a run, not
  a grouping level.
- **Plan** — the drill-down entity inside a project.
- Storage (the two-segment slug) is independent of UI labels: the UI labels
  segment-1 "Project" and treats segment-2 as the run's worktree attribute.

### Plan-centric consolidated view (approved design)

- The **plan** is the unit of intent; a run is just the execution vehicle. A
  plan's lifecycle spans multiple runs (queue re-runs, retries, resumes). The
  panel gets two lenses: **Plans** (default) and **Runs** (debugging a
  specific invocation).
- Workflow spine (`aet-work/workflows/software.json`):
  `plan-approved → implemented → qa-complete → reviewed → secure → synced`.
  Stage records carry these state names, so a plan view can show real
  pipeline progress: which states completed, which failed, where it stalled.
- **Plan detail:** pipeline progress + a consolidated timeline of every
  stage session and test run for the plan across _all_ runs, chronological,
  with run id, worktree, duration, result (retries appear as repeated rows —
  the "all runs combined" view); aggregated tests, environment issues, and
  learning candidates; chips for the runs that touched the plan, linking to
  the run view.
- **Data findings that shape the build:**
  - `plan_file` must be normalized: real values are
    `{REPO_ROOT}/.worktrees/<task>/docs/plans/<plan>.md` (pointing into the
    ephemeral task worktree). Strip to `docs/plans/<plan>.md`, or the same
    plan run from main vs a worktree splits into two "plans".
  - `run_summary` records have no `plan_file`; they carry `task_ids`. Join
    through the global task→plan map (1:1 in current data — no task maps to
    more than one plan) to attribute whole runs that logged no stage
    records.
  - Plan identity = file path; a rename/renumber splits history (v1
    limitation; a stable frontmatter id would fix it, but telemetry doesn't
    capture one).
  - The consolidated view starts at `plan-approved`; earlier human-driven
    steps (aet-plan, PRD, validate) emit no telemetry.
- **Panel-side only:** `plan_file` already exists in the records — the whole
  feature can be built against existing data without touching the
  orchestrator.

### Live session log — feasibility study (deferred, not being built)

- The "execution log" users watch is the **orchestrator's stdout**: its
  status lines plus every spawned agent session's stream (children inherit
  fds — `aet-work/bin/orchestrator:423,478,1206`; no capture anywhere, no
  `--log` flag). `scripts/.aet-work-orchestrator.log` (34,608 lines) is a
  manual redirect of one old run — proof of shape and a dev fixture. Output
  of past runs is unrecoverable, and the panel cannot snoop another
  process's terminal, so this is mostly an orchestrator-side capture
  feature.
- **v1 design (not built):** tee output into the run dir — `{task-id}.log`
  per single-task child + `orchestrator.log` for parent status — via a pump
  thread that mirrors `stdout=PIPE` to both the terminal and the file (the
  live terminal experience is unchanged), sanitizing lines with `_sanitize`
  (`aet-work/lib/telemetry.py:95`). Retention/prune must grow to cover
  `*.log`.
- **Serve/panel:** history needs no API change (`/api/file` already serves
  any archive file; the UI builds the path from `run.dir`). Tail via a small
  offset endpoint `GET /api/log?p=<rel>&offset=N` polled every 1–2s (not
  SSE — no long-lived connections). Live detection: run dir without
  `last-run.json` + fresh log mtime → live badge, keep polling until the
  summary lands. UI: collapsed "Session log" section in run detail + links
  from plan-timeline rows.
- **Build order:** panel viewer first (against the fixture file, zero
  orchestrator changes), then the orchestrator tee — capture only covers
  runs started after it ships; no backfill is possible.
- **v2 direction:** structured session replay instead of raw text — kimi
  emits `TurnBegin`/`StepBegin`/`ThinkPart`; claude supports
  `--output-format stream-json`.

## Roadmap

- [ ] **Stop the pollution at the source** — autouse fixture in
      `tests/conftest.py` that points `AET_TELEMETRY_ARCHIVE_DIR` at a
      per-session tmp dir. Env is inherited by every subprocess spawn, so
      this covers all ~160 call sites at once. _Unblocked 2026-07-11: the
      aet-work run that restricted edits has finished._
- [ ] **Slug redesign** — implement the local git-aware slug in
      `derive_project_slug()` (see "Project slug redesign"), migrate the
      existing archive dirs, update docs.
- [x] ~~**Plan-centric view** — normalization helper, Project → Plan filters,
      plan list + plan detail with the consolidated timeline; run view
      demoted to a tab (see "Plan-centric consolidated view").~~ — **Plans
      lens shipped 2026-07-11 (thp-05):** `plan_file` normalization, task→plan
      join for `run_summary`-only runs, plan list + basic plan card, Runs
      demoted to a tab. **Plan detail shipped 2026-07-12 (thp-06):** pipeline
      spine stepper, consolidated cross-run timeline, aggregated
      issues/learnings, run chips linking to the Runs lens.
- [ ] **Retention CLI** — promote the doc snippet to a proper home (e.g.
      `aet report --prune DAYS`). Must cover `*.log` once session-log
      capture exists, and must never delete the active run dir (check
      `.agents/work-queue.lease` — see Known quirks).
- [ ] **Session log capture (deferred)** — tee design in "Live session log";
      build the panel viewer against the fixture file first.
- [x] ~~Drop `stash@{0}`~~ — the orchestrator popped the stash on 2026-07-11;
      panel files now live in the `aet-panel` worktree.
- [ ] Nice-to-haves: dark mode, per-stage duration chart, link from a run to
      its plan file (the plan view subsumes most of this).

## Files

| File         | Purpose                                            |
| ------------ | -------------------------------------------------- |
| `index.html` | The entire UI (React + Tailwind + shadcn styling). |
| `serve`      | stdlib launcher: static host + archive JSON API.   |
| `README.md`  | This doc — usage, design, findings, decisions.     |

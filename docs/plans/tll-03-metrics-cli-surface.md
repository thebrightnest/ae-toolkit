---
id: tll-03-metrics-cli-surface
size: M
status: queued
blocked_by:
  - tll-02-metrics-aggregation-core
pipeline: standard
security_review: required
security_review_reason: New user-facing command registered in the dispatcher; argument handling (`--since`, `--history-file`) and the no-data degradation path are the correctness boundary a diff scan should see.
docs_sync: required
docs_sync_reason: `aet metrics` is new user-facing surface; the telemetry guide gains the command reference and the projection contract.
---

# Plan: `aet metrics` CLI Surface

## Context

- PRD: `docs/prds/roadmap-p7a-telemetry-learning-loop-prd.md` (R-4, R-6).
- **Ground truth (2026-07-19):** the `aet` dispatcher is an exec-based multicall (`aet-work/bin/aet:29-55` `SUBCOMMANDS`); adding a subcommand is one row + a new executable in `aet-work/bin/` exposing `build_parser()`/`main()` (design note at `bin/aet:5-8`). skills-lint (`scripts/skills-lint:64-109`) derives valid subcommands/flags dynamically from `SUBCOMMANDS` + each target's `build_parser()`, so it needs **zero changes** — but the row and parser must land no later than any skill markdown invoking the command (tll-04 does). Output conventions from `aet-work/bin/status`: `--json` prints the projection dict to stdout and returns before human output; errors go to stderr with `⛔` and rc 1. `aet report` exists but is run-centric and text-only — out of scope here.
- The aggregation core (`aet-work/lib/metrics.py`) lands in tll-02. Blocked by it.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect (roadmap Phase 7a)

## Locked design

- **`aet-work/bin/metrics`** (new, extensionless, executable): lib bootstrap identical to `status:15-17`; `build_parser()` with `--json` (store_true), `--since YYYY-MM-DD` (validated format, invalid ⇒ stderr `⛔` + rc 1), `--history-file` (default `.agents/work-history.jsonl`). `main()` builds `metrics.aggregate(history_file, since=...)` and either prints `json.dumps(projection, indent=2)` (`--json`) or a sectioned human report: **First-pass merge rate**, **Rework**, **Cost per merged task** — overall line + one row per work class, nulls rendered as `-`, `usd` coverage shown as `(n known)`.
- **No-data degradation, not a crash.** Zero settled tasks (missing/empty history) ⇒ an explicit "No settled tasks found" report (human) or the zeroed projection (`--json`), rc 0 — an empty archive is a valid state, not an error. Real argument errors (bad `--since`) are the only rc 1 path.
- **Dispatcher row:** `"metrics": {"target": ("aet-work", "metrics"), "mode": "exec"}` added to `SUBCOMMANDS` in `aet-work/bin/aet`.
- **Docs:** `docs/telemetry-guide.md` gains an `aet metrics` section (human/`--json`/`--since`, projection field contract, null/coverage semantics).

## Rejected Alternatives

- **Extend `aet report` with these aggregations + `--json`** — rejected: `report` is run-centric (spawned/succeeded/failed, wall-clock); the 7a metrics are cross-run settled-task analytics — a separate `metrics` noun keeps both scopes clean and gives 7b's scoreboard a natural sibling.
- **Fail (rc 1) on empty history** — rejected: a fresh project has no settled tasks; the evolve loop (tll-04) must be able to consume the command before the first merge. Explicit no-data, rc 0.
- **`--last <n tasks>` window instead of `--since`** — rejected (PRD Open Question 2, resolved at scope-validation): the evolve loop asks "what changed since the last retro" — a date window answers that directly; task-count windows drift with queue throughput.

## Task List

1. `aet-work/bin/metrics`: parser + `main()` wiring to `metrics.aggregate` — M (traces: R-4)
2. Human report rendering (sections, per-class rows, null/coverage formatting) + no-data path — M (traces: R-4)
3. Dispatcher row in `aet-work/bin/aet` — S (traces: R-4)
4. `docs/telemetry-guide.md` command section — S (traces: R-4)
5. Tests: `tests/test_metrics_cli.py` (new) — M (traces: R-6)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not near-identical additions
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot share a branch — depends on tll-02's module; separate command surface

## Files to Modify

- `aet-work/bin/metrics` (new)
- `aet-work/bin/aet` (one `SUBCOMMANDS` row)
- `tests/test_metrics_cli.py` (new)
- `docs/telemetry-guide.md` (command reference section)

## Validation Steps

- [ ] `make validate` passes; skills-lint green with the new row in place
- [ ] New source coverage — `tests/test_metrics_cli.py` (SourceFileLoader pattern per `tests/test_per_task_cost_rollup.py:20-28`):
  - `test_cli_json_projection_matches_aggregate_shape`
  - `test_cli_human_report_shows_three_metric_sections_and_classes`
  - `test_cli_no_settled_tasks_prints_no_data_rc0`
  - `test_cli_since_filters_window`
  - `test_cli_invalid_since_exits_1_with_stderr`
  - `test_cli_registered_in_dispatcher` (SUBCOMMANDS row resolves to the binary, mirroring `tests/test_aet_multicall.py`)
- [ ] R-trace coverage: R-4 by tasks 1–4; R-6 by task 5; no unknown R-ids
- [ ] Test types: unit (rendering, arg validation) + integration (CLI end-to-end over synthetic fixtures, both output modes)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The dispatcher row, binary, tests, and doc section disappear together — no skill markdown references the command yet (tll-04 lands after), so skills-lint stays green.

## Pipeline

`pipeline: standard` — new user-facing command; standard grouping.

---

*Stage: reviewed*
*Next step: run `aet-cso`*

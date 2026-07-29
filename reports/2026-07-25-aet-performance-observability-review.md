# AET Performance & Observability Review: 2026-07-25

## Context

Follow-up to `reports/2026-07-24-validation-runtime-review.md`, which analysed a **single
two-task batch**. The open question after that report was whether its conclusions generalise —
the standing complaint is that `aet run` re-runs whole-system validation repeatedly, across
several projects, not just in one batch.

This review covers the three projects actually running AET — `aiskills`, `blueocean`,
`manager` — across **every run on disk**: 405 stage sessions, 74.8 h of session time, 1.25 B
tokens, 410 test executions. It adds **950 raw kimi wire logs** from the last 30 days, mapped to
those same three repos via each session's `workDir`.

AET already reads those wire logs: `_emit_wire_test_runs` (`orchestrator.py:600`) calls
`wirelog.extract_test_invocations` at the end of every stage session and writes the results into
the telemetry archive, which is what `aet panel` displays. But it ingests **one filtered slice** —
`Bash` calls matching `is_test_command`, and nothing else. Every other tool call, the turn and
step structure, and all per-call timings are read and discarded. So the wire logs are not an
untapped source so much as an *under-read* one, and the panel is a view of what survived the
filter. Findings 3 and 7 are about the size of what does not.

The headline: **the complaint is real but mis-located, and the reason it has been hard to fix
is that the toolkit's own measurement of it is 49% accurate — and outside `aiskills`, closer to
zero.**

> **Scope note.** `~/.aet/telemetry/thebrightnest` (33 stage sessions, 7.8 h) is excluded: it is
> not one of the projects running AET. Figures below therefore differ from the first cut of this
> report, which included it. Two further differences are unrelated to scope: `test_run` records
> are now deduplicated (finding 3), which changes execution counts and per-run averages but not
> the freshness figures in finding 1; and the archive grew during the review, so totals are a
> 2026-07-25 ~14:20 snapshot rather than the morning's.
>
> **Correction, 2026-07-26.** An earlier version of this report said the telemetry archive never
> ingests the wire logs. It does — see the Context section. Finding 3 has been rewritten: the
> untimed records are not companions of the timed ones, they come from a second emitter that
> transcribes the QA verdict. The measured figures are unchanged; the mechanism behind them is
> not what was described.

## Summary of Findings

1. **Validation *is* re-run repeatedly.** 31% of tasks that already had a green full-suite QA
   run re-ran the full suite afterwards in `reviewed`/`secure`/`synced` — 66 redundant
   executions, 116 min of measured, purely duplicated test time. Median session runs 3 test
   commands; 24% of sessions run more than 8; worst case 114.
2. **But validation is not where the time goes.** Implementation sessions are **61.6% of session
   time and 55.6% of tokens**. Measured test execution is 8.6%; roughly 17% once the detection
   gap below is corrected. Post-implementation stages
   (`reviewed`/`secure`/`synced`) are **32.2% of time and 36.1% of tokens** — a bigger block
   than all testing, and largely unexamined.
3. **The test-run telemetry sees 49% of test time, and 0% of it outside `aiskills`.**
   `wirelog.is_test_command` anchors its regexes at the start of the command string, so it misses
   `cd <worktree> && …` (1,248 invocations, 804 min), `.venv/bin/python -m pytest` (218, 102
   min), `source … && …`, `npx`, and every non-Python-non-`make` runner. **1,140 of 2,249
   measured minutes are invisible.** Per project: `aiskills` 50%, `blueocean` 5%, `manager` 0%.
4. **A quarter of what the panel calls a test run is the agent's self-report.** Two emitters
   write `test_run` records and nothing distinguishes them: one observes the wire log, one
   transcribes the QA verdict with `start_time=None, end_time=None, exit_code=0` hardcoded. The
   claimed half — 97 of 410 executions — can never carry a duration and can never record a
   failure, which lifts the apparent pass rate from 80% to 85%. For **74** of them there is no
   observed twin at all.
5. **Localized validation exists only in this repo.** `change_scope` is consumed solely by this
   repo's Makefile and its path table is hardcoded to this repo's layout. Other projects fall
   back to prose guidance in `aet-qa`. Measured: `aiskills` runs 128/401 executions impact-scoped
   (32%); `blueocean` and `manager` have **0 of 9**.
6. **10.6% of stage sessions fail**, burning 8.1 h (10.8% of all session wall clock) — and 41 of
   43 failures carry no `failure_class`.
7. **Turn-level telemetry is not missing — it is unharvested.** Both parked ideas
   (`docs/ideas/cfg-01-session-efficiency.md`,
   `docs/ideas/deterministic-qa-freshness-suppression.md`) are blocked on "turn-level telemetry
   that the toolkit does not emit." The kimi wire log already carries `turnId`, `step.begin`/
   `step.end`, and paired per-tool-call timestamps. `wirelog.py` already reads this file — it
   just filters everything except test commands.

## Where the Time and Tokens Actually Go

Three projects, all history, 405 stage sessions:

| Stage(s) | n | hours | % time | Mtok | % tokens |
|---|---:|---:|---:|---:|---:|
| `plan-approved`+`implemented` | 129 | 46.0 | **61.6%** | 695.2 | **55.6%** |
| `reviewed` | 124 | 13.8 | 18.4% | 232.3 | 18.6% |
| `reviewed`+`secure` | 56 | 6.3 | 8.4% | 118.1 | 9.5% |
| `synced` | 42 | 3.7 | 4.9% | 93.1 | 7.5% |
| `implemented` | 22 | 3.0 | 4.0% | 69.4 | 5.6% |
| `qa-complete` | 25 | 1.7 | 2.2% | 34.5 | 2.8% |
| `secure` | 7 | 0.4 | 0.5% | 6.9 | 0.6% |
| **Total** | **405** | **74.8** | 100% | **1249.6** | 100% |

The corpus is overwhelmingly `aiskills` — 377 of 405 stage sessions (69.9 h, 1231 Mtok).
`blueocean` contributes 15 sessions (2.2 h) and `manager` 13 (2.7 h, 18.6 Mtok), all from
2026-07-12/13. Cross-project claims below therefore rest on a small n for the other two, and are
flagged where that matters.

The 2026-07-24 report's single-batch conclusion holds at corpus scale: **implementation
dominates**. What that report could not see, because it looked at one batch, is the size of the
**post-implementation block** — `reviewed` + `reviewed`+`secure` + `synced` + `secure` is
**32.2% of session time and 36.1% of tokens**, spread over 229 sessions averaging ~379 s and
~2.0 M tokens each. `reviewed` alone burns 232 M tokens.

Recent throughput (64 tasks since 2026-07-20): median **25.5 min**, mean 27.1 min, **2.9
sessions**, **11.0 M tokens** per task.

## Finding 1: The Redundant Re-Run Is Real and Measurable

ADR-025 introduced a freshness signal so gate stages trust a fresh QA verdict instead of
re-running the suite. It is enforced **in prose** — `_freshness_clause`
(`src/aet/cli/orchestrator.py:388`) injects a sentence; `AET_QA_FRESHNESS` is exported but has
no runtime consumer. Measured compliance across all history:

| | |
|---|---:|
| Tasks with a green full-suite QA execution | 102 |
| …that re-ran the full suite in `reviewed`/`secure`/`synced` anyway | **32 (31%)** |
| Redundant full-suite executions | **66** |
| Measured duplicated test time | **116 min** |

Full-suite executions by stage, all history:

| Stage | executions | timed | total | avg (timed) |
|---|---:|---:|---:|---:|
| `qa-complete` | 165 | 89 | 176.1 min | 119 s |
| `synced` | 47 | 47 | 88.2 min | 113 s |
| `reviewed` | 45 | 45 | 80.9 min | 108 s |
| `implemented` | 13 | 13 | 20.4 min | 94 s |
| `secure` | 1 | 1 | 1.8 min | 108 s |

**93 full-suite executions (171 measured min) happen in stages downstream of QA.** The prose
clause is honoured roughly 69% of the time. This is exactly the revisit trigger written into
`docs/ideas/deterministic-qa-freshness-suppression.md`: *"or when a concrete run demonstrates
the agent skipping a safe suppression often enough to matter."*

Per-session repetition, from wire logs (539 sessions in the last 30 days that ran at least one
test command): median **3** test invocations, mean 6.4, **49% run more than 3**, **24% run more
than 8**, worst case **114 test commands in one session**.

## Finding 2: The Monitoring Is 49% Accurate — and 0% Outside aiskills

`wirelog.is_test_command` matches against anchored regexes (`^\s*pytest`, `^\s*python3?\s+-m\s+
pytest`, `^\s*make\s+…`). Verified against the live code:

| Command | detected? |
|---|---|
| `pytest tests/cli -q` | yes |
| `make validate` | yes |
| `.venv/bin/python -m pytest tests/cli` | **no** |
| `cd /repo/.worktrees/x && .venv/bin/python -m pytest tests/ -q` | **no** |
| `cd /repo && make validate` | **no** |
| `source .venv/bin/activate && make validate` | **no** |
| `npx vitest run src/foo.test.tsx` | **no** |
| `npm run test:renderer` / `yarn test` / `pnpm test` | **no** |
| `poetry run pytest` / `uv run pytest` | **no** |
| `bundle exec rspec` / `phpunit` / `dotnet test` / `gradle test` | **no** |

Scanning the 950 wire logs from the last 30 days that belong to these three repos, for anything
test-shaped:

| | invocations | time |
|---|---:|---:|
| Detected by `wirelog` | 1,379 | 1,110 min |
| **Missed** | **2,074** | **1,140 min** |
| **Coverage** | **40%** | **49%** |

Per project the picture is much worse than the aggregate suggests:

| Project | invocations | detected | coverage (time) |
|---|---:|---:|---:|
| `aiskills` | 3,179 | 1,376 | 50% |
| `blueocean` | 164 | 3 | **5%** |
| `manager` | 110 | 0 | **0%** |

Top missed shapes: `cd … && <test>` (1,248 calls / 804 min), `.venv/bin/python …` (218 / 102
min), `source … &&` (78 / 78 min), `make` in a compound command (22 / 15 min), `. .venv/bin/
activate &&` (13 / 15 min), `npx` (65 / 11 min).

The orchestrator runs agents **inside git worktrees**, so `cd <worktree> && …` is the *normal*
shape of an agent's shell call. The detector is blind to its own most common case.

Three consequences:

- **Every prior estimate of validation cost is an undercount.** The 2026-07-24 report put
  pytest at 9.2% of the dominant `cfg-01` session. Re-profiling that same session from its wire
  log: of 780 s of Bash time, **671 s was test execution** — `pytest -n 1` (216 s), `make
  validate` (161 s), and four `cd … && pytest` runs (88.9 / 82.3 / 67.9 / 54.8 s). That is
  **38% of the session**, not 9.2%. Telemetry recorded 2 of those 6 runs.
- **Outside `aiskills`, validation cost is not measured at all.** `manager` has 110 test-shaped
  invocations in the wire log and 0 detected; `blueocean` 164 and 3. Whatever those projects
  spend on testing, the telemetry archive does not know it — which is also why finding 5's
  cross-project comparison has so little to work with.
- **The `vre-01` improvement is invisible.** `classify_test_scope` labels any `make` target
  `full-suite` by construction (`telemetry.py:77-79` — make targets are never paths). Now that
  `make validate` selects targeted pytest paths internally, every targeted run is still
  reported as `full-suite`. There is currently **no way to observe whether vre-01 worked.**

One more artefact worth naming: in that session the agent ran `.venv/bin/python -m pytest -n 1`
— the **full suite, serially, 216 s** — longer than `make validate` itself. Nothing in the
toolkit prevents an agent from bypassing the project's validation entry point for a slower one,
and nothing measures it when it happens.

## Finding 3: One Record Type, Two Provenances — Observed Runs and Claimed Runs

`test_run` records come from two emitters that write the same record type and are not
distinguished by any field:

- **`_emit_wire_test_runs`** (`orchestrator.py:603`) — *observed*. Derived from the wire log, so
  it carries real start/end timestamps and the real exit code, and never carries test counts.
- **`_emit_test_run_from_verdict`** (`orchestrator.py:711`) — *claimed*. Derived from the QA
  agent's own verdict. It passes `start_time=None, end_time=None, exit_code=0` literally, so
  every such record has a null duration and `result: "success"` **by construction**, and it only
  fires on a passing verdict.

The corpus splits cleanly along that line — no record mixes the two shapes:

| | Observed (wire) | Claimed (verdict) |
|---|---:|---:|
| Records | 313 | 112 |
| Carry a duration | 313 | **0** |
| Carry test counts | 0 | 112 |
| Recorded as `success` | 250 (80%) | **112 (100%)** |
| Stage | all stages | **all `qa-complete`** |

After deduplicating on `(run_id, task_id, stage, scope, test_command)`, 15 of the claimed records
collapse into an observed twin, leaving **410 distinct executions: 313 timed, 97 untimed
(24%)** — 76 of them at `qa-complete`.

Three consequences, in ascending order of seriousness:

1. It skews any average computed over raw records. The first cut of this report quoted a 63 s
   mean for `qa-complete` full-suite runs by dividing total time by record count; the correct
   mean over timed executions only is **119 s**.
2. It inflates the apparent pass rate. Observed runs succeed 80% of the time; the mixed corpus
   reads **85%**, because the claimed half cannot record a failure.
3. **74 execution groups have a claimed record and no observed twin at all** — the panel shows a
   test run that AET never saw run. The reported commands are ordinary (`make validate` ×35,
   `python3 -m pytest tests/ -q` ×13, `make test` ×8) and `is_test_command` matches them, so the
   likely explanation is that the agent's actual shell invocation was shaped differently from the
   command it wrote in its verdict — exactly the `cd … && make validate` form finding 2 shows the
   detector dropping. That cannot be confirmed after the fact, because the `stage` record
   persists no session identifier: there is no key linking a telemetry record back to the wire
   log it came from. Adding one is a one-field change and a precondition for auditing any of this.

The panel presents both kinds side by side as equivalent test runs. A quarter of what it shows is
the agent's self-report, unfalsifiable and pre-marked green.

> **Update (2026-07-28, `tap-05`):** fixed. `test_run` records now carry a required `source`
> (`"wire"` observed / `"verdict"` claimed), the verdict emitter no longer hardcodes
> `exit_code: 0`, and every consumer declares which population it reads — timing and pass rate
> over observed, counts over claimed, each labeled where it is displayed (ADR-051).
>
> The 80% / 85% figures above stand: re-measured on 2026-07-28 the archive holds 495 `test_run`
> records, 360 observed (80% pass, 359 decided) and 135 claimed (100% pass), blending to 85%.
> Published pass rates should be read as the observed 80% — a correction, not a regression.
>
> All 495 of those records predate the change and carry no `source`, so per ADR-051 decision 5
> they are provenance-unknown and are **not** backfilled: the split above is recoverable only by
> field signature, which is exactly the inference the decision refuses to make the forward
> contract. The consequence is that provenance-filtered surfaces read `—` over historical data
> and begin populating with runs recorded after this change. Any longitudinal series spanning
> 2026-07-28 has to say so.

## Finding 4: Targeted Validation Is aiskills-Only

`src/aet/change_scope.py` is real, works, and is the right design. It is also **not reachable
from any other project**:

- Its only consumer is this repo's `Makefile:105-108`. There is no `aet` subcommand exposing it
  (`aet --help` has no `scope`/`validate` entry).
- `_PATH_TARGETS` (`change_scope.py:22-49`) is a hardcoded table of *this repo's* layout —
  `src/aet/backends/` → `tests/backends`, and 26 more. Nothing is configurable.

Every other project therefore relies on the prose in `skills/aet-qa/SKILL.md:47` ("Default to
impact-scoped tests… map them to test files via project conventions or heuristics") — AI
discretion, the failure mode this toolkit otherwise designs against. The measured outcome:

| Project | impact-scoped | full-suite | unknown | % impact-scoped |
|---|---:|---:|---:|---:|
| `aiskills` | 128 | 262 | 11 | 32% |
| `blueocean` | 0 | 5 | 0 | 0% |
| `manager` | 0 | 4 | 0 | 0% |

**Read this one with care.** `blueocean` and `manager` contribute 9 executions between them,
all from a two-day window in mid-July, and — per finding 2 — their wire logs show 274
test-shaped invocations that telemetry never recorded. The directional claim is well supported
by the code (`change_scope` provably cannot run outside this repo). The *rate* is not
established by 9 data points. Landing recommendation 1 is what would make it measurable.

## Finding 5: Failed Sessions Cost 10.8% of Wall Clock

| | |
|---|---:|
| Failed stage sessions | 43 / 405 (**10.6%**) |
| Wall clock burned | **8.1 h** (10.8%) |
| Classified with `failure_class` | 2 |

`failure_class`, `plan_snapshot`, `attempt`, and `actual_stages` shipped with `ppt-04` on
2026-07-24 and only populate on runs after that date — so this is a coverage gap that time will
close, not a bug. **`cost_estimate` is different: 0 of 405 records across all history.**
`orchestrator.py:596` sources it from `usage.get("cost_usd")`, which the kimi extractor never
provides. Token spend is observable; dollar spend is not.

## Finding 6: Turn-Level Telemetry Already Exists

Both parked ideas share one revisit trigger: *"pick this up when turn-level telemetry lands."*
It has already landed — in the wire log, unharvested. Profiling `cfg-01` session 1 (the
29-minute session the idea is written about) took one pass over one file:

| | |
|---|---:|
| Session span | 29.2 min |
| Tool calls | 198 (`Edit` 67, `Bash` 58, `Read` 50, `Grep` 12, `TodoList` 7, `Write` 4) |
| Steps (`step.begin`/`step.end`) | 149 |
| Bash time | 780 s (**44.5%**) — of which 671 s was test execution |
| Model / non-Bash time | 973 s (**55.5%**) |

`Edit`, `Read`, `Grep`, and `Write` cost ~0 s each — they are token costs, not time costs. The
session splits roughly **45% shell / 55% model**, and the shell half is almost entirely tests.
That is a directly actionable profile, and it contradicts the "context re-read" hypothesis the
parked idea speculated about.

The wire schema carries `turnId`, `stepUuid`, `traceId`, and paired `time` values on every
`tool.call`/`tool.result`. `_emit_wire_test_runs` (`orchestrator.py:603`) already receives the
`session_dir` and iterates these events. Extending it from "emit test runs" to "emit a per-tool
aggregate per session" is a small change to an existing code path, not new instrumentation.

The session→project mapping used throughout this report comes from the same place:
`~/.kimi-code/sessions/*/*/state.json` carries `workDir`, which resolves to a repo root once
`.worktrees/<task>` is stripped. Nothing in AET reads it today.

## Finding 7: The Telemetry Archive Is Polluted

`~/.aet/telemetry/` holds **482 project directories**, of which roughly 468 are test and
rehearsal leakage: 437 `nsr-07-rehearsal-*`, 28 `tmp*`, 3 `repro-stall-*`, plus `tests` and
`test_runlogger_defaults_under_0`. 43 MB total. It grew by 13 directories during the few hours
this review took, so the leak is live, not historical. `thp-01-test-telemetry-isolation` merged,
but the debris remains and any cross-project query has to hand-filter it. `aet report --prune`
exists but is not scoped to this class of directory.

## Recommendations

Ordered by leverage. Items 1–3 are the ones that change the answer to "why does `aet run` keep
re-validating everything."

### 1. Fix the test-command detector — prerequisite for everything else

`wirelog.is_test_command` should tokenise on `&&`/`;`/`|`, take the last segment, strip
`cd … &&`, `source … &&`, `. … &&`, leading env assignments (`PYTHONPATH=… cmd`), path prefixes
(`.venv/bin/`, `./vendor/bin/`), and runner wrappers (`poetry run`, `uv run`, `npx`, `npm run`,
`yarn`, `pnpm`, `bundle exec`, `time`). Add the runners the list lacks: `rspec`, `phpunit`,
`php artisan test`, `dotnet test`, `gradle test`, `unittest`.

Three companion fixes belong with it:

- `classify_test_scope` must stop reporting `make validate` as `full-suite`. The honest fix is
  for `make validate` to emit its resolved `PYTEST_TARGETS` (`change_scope` already prints them
  under `--explain`) and for the scope classifier to read that, so the `vre-01` improvement
  becomes observable.
- Mark provenance on `test_run`. Add a `source` field (`"wire"` / `"verdict"`) so observed and
  claimed runs are separable, and stop counting verdict-derived records in duration or pass-rate
  aggregates. Better still: once the detector is fixed, reconcile the verdict against the
  observed run and keep the verdict only for the test *counts* it uniquely carries.
- Persist the session directory on the `stage` record. Without it no telemetry record can be
  traced back to the wire log that produced it, which is why finding 3's 74 orphans can be
  characterised but not explained.

**Cost:** small, localized, well-tested surface. **Value:** every performance number the
toolkit reports is currently wrong by roughly 2× in `aiskills` and unbounded elsewhere. Nothing
downstream can be trusted until this lands.

### 2. Un-defer `vre-04` — deterministic freshness suppression

Its stated revisit trigger is met: 31% of tasks, 66 executions, 116 min of measured duplicated
work. The idea doc's own condition was "efficiency-only and currently unmeasured" — it is now
measured. Follow the path the doc already lays out: ADR extending ADR-025 (suppression becomes
enforced, `_require_passing_verdict` untouched, bias-to-`RUN` preserved), then the plan.

Note the ordering dependency: with the Finding-2 detector fix, the true redundancy figure is
likely **higher** than 31%, since `cd … && pytest` re-runs in `reviewed`/`synced` are currently
invisible. Landing (1) first sizes (2) correctly.

### 3. Make `change_scope` portable — an `aet scope` subcommand

Expose the existing module as `aet scope [--explain] [--json]`, and move `_PATH_TARGETS` from a
hardcoded list into project config (the `cfg-*` config work just landed the resolution layer).
Default to the current fail-toward-full-suite behaviour when no map is declared. Then have
`aet-qa` call `aet scope` instead of instructing the agent to derive impact scope by heuristic.

This is what turns "aiskills has targeted validation" into "AET has targeted validation," and
it replaces prose discretion with a code-computed answer — consistent with ADR-049's own framing
of `change_scope` as *the* authority for validation scope.

### 4. Examine the post-implementation 32%

229 sessions, 24.1 h, 451 M tokens in `reviewed`/`secure`/`synced`. This block has never been
profiled and is larger than all test execution combined. With (1) landed, the wire logs will
show whether those sessions are re-reading the full plan and diff from cold each time — the
grouped-session question the `cfg-01` idea raised but could not answer.

### 5. Harvest per-tool telemetry from the wire log

Extend `_emit_wire_test_runs` into a general per-session tool aggregate (calls and seconds by
tool name, turn count, step count), and record the session's `workDir`-derived project while
you are in there. This is a modest extension of an existing code path and it retires the
"blocked on turn-level telemetry" note on both parked ideas.

### 6. Housekeeping

- Populate `cost_estimate`, or drop it from the schema and report tokens only. 0/405 is worse
  than absent — it looks like a supported field.
- Extend `aet report --prune` to sweep leaked project directories (`tmp*`, `*-rehearsal-*`,
  `tests`), or make test isolation write outside `~/.aet/telemetry/` entirely. The leak is
  active, so pruning alone will not hold.

## What This Does *Not* Recommend

- **Skipping validation in later stages by stage name.** Same conclusion as 2026-07-24:
  `synced` is not reliably code-free, and the decision belongs in `change_scope`, keyed on the
  change set.
- **Chasing the pytest suite time further.** Post-`vre-02`/`vre-03` the suite runs 1,220 tests
  in **163 s / 147.0 s / 148.8 s** across three consecutive `-n auto --dist=loadgroup` runs on
  2026-07-25 (first run cold), down from the 238 s baseline. The remaining wins are in *how
  often* it runs, not how fast.

  Worth flagging: `vre-02`'s divergence summary records a mean of **~103.6 s** over 10 runs.
  Today's warm runs sit ~45% above that. Either the measurement conditions differed or
  something has regressed since — the gap is unexplained and small enough to be machine load,
  but it should be re-measured before the 103.6 s figure is quoted anywhere as the baseline.

## Appendix: Method

- Scope: `aiskills`, `blueocean`, `manager`. `thebrightnest` excluded as not an AET project.
- Telemetry: every `*.jsonl` under `~/.aet/telemetry/{aiskills,blueocean,manager}/`. Snapshot
  taken 2026-07-25 ~14:20; the archive grew by 6 stage sessions during the review.
- `test_run` deduplication: grouped on `(run_id, task_id, stage, scope, test_command)`.
  Wire-derived (timed) records are distinct executions; a verdict-derived record sharing a group
  with one is treated as the same execution seen twice and discarded (15 cases). Where a group
  holds only verdict-derived records, it is counted as one execution of unknown duration (74
  cases). Provenance was verified by field signature and confirmed against the two emitters:
  wire-derived records carry timestamps and no test counts (313/313), verdict-derived carry
  counts and no timestamps (112/112) — the split is exact.
- Wire logs: `~/.kimi-code/sessions/*/*/state.json` → `workDir` → repo root (stripping
  `.worktrees/<task>`), keeping only the three project roots; then every `agents/*/wire.jsonl`
  under those sessions modified in the last 30 days (950 files). Bash `tool.call`/`tool.result`
  paired on `toolCallId`; duration from the top-level `time` field (epoch ms).
- Detection gap measured by running the live `aet.wirelog.is_test_command` against every
  test-shaped command found by a deliberately broader regex. `git`-headed commands were dropped
  from that set after inspection showed commit messages quoting test results (`"425/425 tests
  pass, make validate green"`) matching the broad pattern — a conservative exclusion that also
  drops a handful of genuine `git … ; make validate` compounds.
- Suite timing: `.venv/bin/python -m pytest tests/ -q -n auto --dist=loadgroup` on an M-series
  Mac, repo clean, three consecutive runs (163 s cold, then 147.0 s, 148.8 s).
- All three projects ran the `kimi` agent CLI (374/377 `aiskills` stage records; 100%
  elsewhere), so cross-project differences are not agent-CLI artefacts.

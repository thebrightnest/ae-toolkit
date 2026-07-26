# PRD: Telemetry Adapter Parity & Test-Run Fidelity

*Stage: scope-validated*
*Next step: `aet sprint add` the `tap-*` plans, then run `aet run-one` or `aet run`*

## Overview

AET's test-run telemetry is kimi-shaped and roughly half blind. `wirelog.py` parses only kimi's
session schema, and `orchestrator.py` resolves a session directory only when the adapter is
`kimi` — so **any other CLI emits zero observed `test_run` records by construction**. All three
Claude Code sessions in the archive confirm it: 0 test runs, 0 tokens. Independently,
`is_test_command` anchors its regexes at the start of the command string, so the ordinary
`cd <worktree> && make validate` shape an orchestrator agent actually runs is not recognised —
49% of measured test time is invisible in kimi sessions and 96% in Claude Code transcripts.

This PRD makes test-run extraction adapter-neutral and makes what it records honest: one shared
runner registry behind both detection and scope classification, a dispatched session-log reader
per agent CLI, provenance marking so observed runs are separable from the QA agent's
self-reported ones, and a session identifier on stage records so any row can be traced back to
the log that produced it.

**Intake triage.** Three items here are demonstrable defects in existing code (compound-command
detection, `make`-target scope classification, and rework counting `test_run` records against
ADR-035's own wording); the rest is new capability — an extension point, a second reader, and two
schema fields. `aet-bug-report`'s targeted-fix path cannot deliver a module boundary, and fixing
the regex alone would harden the kimi assumption it sits on. Classified as an **enhancement with
embedded defect remediation** and planned as one sequence.

## Goals

- **G-1**: Test-run telemetry has the same fidelity on Claude Code as on kimi — same records,
  same fields, same timing basis.
- **G-2**: Recorded test invocations reflect what agents actually run, closing the detection gap
  on both CLIs.
- **G-3**: Observed and claimed test runs are distinguishable, so duration and pass-rate
  aggregates stop mixing measurement with self-report.
- **G-4**: Every telemetry record is traceable to the session log that produced it.
- **G-5**: The `vre-01` targeted-validation win becomes observable instead of being masked by
  scope misclassification.
- **G-6**: The factory metrics measure pipeline outcomes, not shell commands inside a session, so
  they stop reporting ≈1% and stop moving when test detection improves.

## Non-Goals

- Adding support for agent CLIs beyond `kimi` and `claude`. The dispatch seam makes a third
  reader cheap; this PRD does not write one.
- Harvesting non-test telemetry from session logs (per-tool call/second aggregates, turn and
  step counts). That remains the parked `docs/ideas/cfg-01-session-efficiency.md` idea; this PRD
  only builds the seam it would use.
- Changing validation **behaviour**. No freshness suppression, no stage-based skipping, no
  change to what gets run or when. `docs/ideas/deterministic-qa-freshness-suppression.md`
  (`vre-04`) stays deferred; this PRD is a precondition for evaluating it, not a substitute.
- Backfilling or reconciling the ~425 historical `test_run` records already on disk. Records
  written before this change carry no `source` field and are read as provenance-unknown.
- Redesigning the telemetry archive layout, retention, or the panel's information architecture.

## Requirements

- **R-1**: `is_test_command` recognises a test invocation inside compound and wrapped shell
  commands — separator tokenisation (`&&`, `;`, `|`), `cd …`/`source …`/`. …` prefix stripping,
  leading environment assignments, interpreter path prefixes (`.venv/bin/`, `./vendor/bin/`),
  and runner wrappers (`poetry run`, `uv run`, `npx`, `npm run`, `yarn`, `pnpm`, `bundle exec`,
  `time`).
- **R-2**: The recognised-runner set covers `rspec`, `phpunit`, `php artisan test`,
  `dotnet test`, `gradle test`, and `python -m unittest` in addition to the v1 list.
- **R-3**: `is_test_command` and `telemetry.classify_test_scope` resolve commands through one
  shared runner registry, so every command the detector recognises is also classifiable and the
  two lists cannot drift.
- **R-4**: Session-log test extraction is reached through a single adapter-dispatched interface,
  mirroring how `usage.parse_usage` dispatches on `agent_cli`. The kimi reader sits behind it
  with byte-identical output for the same input.
- **R-5**: A Claude Code reader extracts test invocations from
  `~/.claude/projects/<cwd-slug>/<sessionId>.jsonl`, pairing `tool_use` and `tool_result` blocks
  on `tool_use_id`, deriving timestamps from the ISO-8601 `timestamp` field and exit status from
  `is_error`.
- **R-6**: The orchestrator resolves an adapter-neutral session reference in place of the
  kimi-only `session_dir`, so observed `test_run` records are emitted for every supported CLI.
- **R-7**: `test_run` records carry a `source` field distinguishing observed (`"wire"`) from
  claimed (`"verdict"`) provenance; records lacking the field are treated as unknown provenance.
- **R-8**: Every surface that aggregates `test_run` records states which provenance it reads.
  Timing and pass-rate aggregates read observed records only; test-**count** aggregates
  (`tests_total`/`tests_passed`/`tests_failed` in `src/aet/panel/index.html` and
  `src/aet/cli/desk.py`) read claimed records, which are the only ones carrying counts, and say
  so. Lists that show individual records label each one's provenance.
- **R-9**: `stage` records persist the session identifier of the session that produced them, so
  any telemetry record can be traced to its originating session log.
- **R-10**: `classify_test_scope` reports the real scope of a `make validate` run by reading the
  targets `change_scope` resolved, rather than labelling every `make` target `full-suite`.
- **R-11**: Token capture for Claude Code sessions is verified end to end against a live
  session; any defect found is fixed, and if none is found the verification is recorded.
- **R-12**: The factory metrics read `stage` telemetry records only. `test_run` records count
  toward neither the failed-record clause nor the **Rework** count, so **First-Pass Merge** keeps
  `merged` state, required verdicts passing, no failed **stage** record, and no rework — where
  rework counts repeated **stage** records plus `failed → *` re-entries. This lands **before** the
  detection work so the metrics do not move as a side effect of seeing more test runs, and the
  before/after re-baseline is recorded with the two clauses attributed separately.
- **R-13**: Consumers that key on `scope: "full-suite"` — `src/aet/cli/mine_learnings.py`
  counts `full_suite_runs` — are re-baselined for the corrected classification, so R-10 does not
  silently change which learnings are mined.

## User Stories

- As a toolkit maintainer running AET on Claude Code, I want the same test-run records I get on
  kimi, so that switching agent CLI does not silently switch off half my telemetry.
  (satisfies: R-4, R-5, R-6)
- As a toolkit maintainer reading `aet panel`, I want to know which test runs AET actually
  observed and which the QA agent merely reported, so I do not read a pre-marked-green
  self-report as a measurement. (satisfies: R-7, R-8)
- As a toolkit maintainer investigating an anomalous record, I want to open the session log it
  came from, so that discrepancies are explainable instead of permanently orphaned.
  (satisfies: R-9)
- As a toolkit maintainer sizing validation work, I want recorded test time to match the test
  time agents actually spend, so that efficiency decisions rest on real numbers.
  (satisfies: R-1, R-2, R-3)
- As a toolkit maintainer who shipped `vre-01`, I want targeted `make validate` runs to be
  recorded as impact-scoped, so I can tell whether the change worked. (satisfies: R-10)
- As a toolkit maintainer comparing agent CLIs on cost, I want Claude Code sessions to record
  tokens like kimi sessions do, so cross-CLI comparison is possible at all. (satisfies: R-11)
- As a toolkit maintainer watching the first-pass-merge rate, I want it to count pipeline
  outcomes rather than shell commands inside a session, so it stops reading ≈1% and stops moving
  every time test detection improves. (satisfies: R-12)
- As a toolkit maintainer relying on mined learnings, I want scope reclassification not to
  quietly change which patterns get mined, so learning output stays trustworthy across the
  change. (satisfies: R-13)

## Acceptance Criteria

- [ ] `is_test_command("cd /path/to/worktree && make validate")` returns `True`, as do the
      `source …`, `.venv/bin/python -m pytest`, leading-env-assignment, `time`, and
      `npx`/`poetry run`/`uv run` wrapper forms. (satisfies: R-1)
- [ ] Each runner added in R-2 is recognised by `is_test_command` and classified by
      `classify_test_scope`, verified by table-driven tests. (satisfies: R-2, R-3)
- [ ] Removing a runner from the shared registry makes both the detection test and the
      classification test fail, proving there is one list and not two. (satisfies: R-3)
- [ ] Replaying a captured kimi session fixture through the dispatched interface yields output
      identical to the pre-change `extract_test_invocations`. (satisfies: R-4)
- [ ] Replaying a captured Claude Code transcript fixture yields test invocations with correct
      commands, paired start/end timestamps, non-null durations, and exit codes derived from
      `is_error`. (satisfies: R-5)
- [ ] An orchestrated stage session run under `claude` writes at least one `test_run` record
      with `source: "wire"` and a non-null `duration_seconds`. (satisfies: R-6)
- [ ] Every `test_run` record written by `_emit_wire_test_runs` carries `source: "wire"`; every
      record written by `_emit_test_run_from_verdict` carries `source: "verdict"`.
      (satisfies: R-7)
- [ ] Over a fixture containing both provenances: timing aggregates match the observed-only
      figures and do not move when claimed records are added; count aggregates match the
      claimed-only figures and do not move when observed records are added; every record shown
      individually is labeled with its provenance. (satisfies: R-8)
- [ ] Every `stage` record carries a non-null session identifier, and a documented lookup
      resolves it to a session-log path for both CLIs. (satisfies: R-9)
- [ ] A `make validate` run narrowed by `change_scope` to a subset of test paths is recorded
      with `scope: "impact"`; an unnarrowed run is still recorded `full-suite`. (satisfies: R-10)
- [ ] A live Claude Code stage session records a non-null `token_count`, or the verification
      records why it cannot with a reproduction. (satisfies: R-11)
- [ ] A task whose telemetry contains a failed `test_run` but a clean stage history and passing
      verdicts is reported as a first-pass merge by `track_record.is_clean_merge`,
      `aet desk --eligibility`, and `aet metrics`; a task with a failed **stage** record still is
      not. (satisfies: R-12)
- [ ] `rework_count` for a task with one stage record and three `test_run` records in the same
      stage is `0`, not `3`; repeated **stage** records and `failed → *` transitions still count.
      (satisfies: R-12)
- [ ] The first-pass-merge rate and rework counts over the existing archive are recorded before
      and after R-12, with the delta attributed separately to the rework clause and the
      failed-record clause. (satisfies: R-12)
- [ ] `mine_learnings` `full_suite_runs` counts are re-derived over a fixture containing both
      `full-suite` and newly `impact`-scoped `make validate` records, and the mined-learning
      output difference is documented rather than discovered later. (satisfies: R-13)

## Technical Notes

**Code anchors.** `src/aet/wirelog.py` (kimi-only schema, anchored regexes at `_TEST_RUNNER_RES`
lines 29-38); `src/aet/cli/orchestrator.py:901-903` (`session_dir` gated on
`adapter.name == "kimi"`), `:603` (`_emit_wire_test_runs`), `:711`
(`_emit_test_run_from_verdict`, which passes `start_time=None, end_time=None, exit_code=0`
literally); `src/aet/telemetry.py:40` (`classify_test_scope`), `:62` (`_test_runner_args`, whose
docstring already notes it "mirrors the wire-extraction match list" — the duplication R-3
removes), `:192` (`stage_record`), `:328` (`test_run_record`); `src/aet/cli_adapter.py:57`
(`ADAPTERS`); `src/aet/usage.py:43` (`parse_usage`, the dispatch pattern R-4 mirrors).

**Claude Code schema, verified 2026-07-26.** Transcripts live at
`~/.claude/projects/<cwd-slug>/<sessionId>.jsonl`. Assistant records carry
`message.content[]` blocks of `type: "tool_use"` with `name: "Bash"`, `id`, and
`input.command`; the paired user record carries a `type: "tool_result"` block with
`tool_use_id`, `is_error`, and `content`. Every record additionally carries `timestamp`
(ISO-8601), `sessionId`, `cwd`, and `gitBranch`. A throwaway extractor written against this
schema during scope validation read 70 transcripts and paired 170 test-shaped Bash calls with
correct durations, so the schema above is confirmed against real data rather than inferred. The
script itself was not kept — the schema description here is the deliverable, and `tap-03` rebuilds
the extractor as tested source.

**Asymmetries worth exploiting.** Claude's `cwd` on every record removes the `state.json`
sidecar lookup kimi needs for project mapping, and the result envelope's `session_id` is a
cleaner anchor than kimi's regex-scraped `kimi -r` resume hint. The interface should not force
Claude's reader down kimi's path-reconstruction route.

**Structural decisions requiring ADRs** (authored during scope validation, per the convention
that intake refuses plans citing unresolvable ADRs):

- **ADR-050** — session-log extraction as a per-adapter extension point; establishes that a CLI
  is only fully supported once it supplies a reader.
- **ADR-051** — `test_run` provenance; observed and claimed records are not interchangeable and
  must not be aggregated together.
- **ADR-052** — factory metrics read `stage` records only, not `test_run`; refines ADR-035.

**Metric-continuity conflict, resolved — and a defect found while resolving it.** ADR-035 defines
**First-Pass Merge** as requiring no failed `stage`/`test_run` record and no **Rework**, where
rework is "repeated stage runs (stage telemetry records beyond the first for any stage name)".
Both clauses read `track_record.iter_telemetry_task_records`, which yields `stage` **and**
`test_run` records (`track_record.py:74`). For the failure clause that is intentional. For rework
it is not: `_repeated_stage_count` (`:103`) groups every yielded record by its `stage` field, and
`test_run` records carry one — so each extra `make validate` in a stage scores +1 rework, against
ADR-035's own written definition.

Measured over the 127 tasks with stage/`test_run` telemetry in the three AET projects:

| Clause | Current (stage + `test_run`) | Stage records only |
| --- | --- | --- |
| Tasks with rework > 0 | **121 (95%)** | 25 (20%) |
| Tasks with a failed record | 52 | 27 |
| **Passing both telemetry clauses** | **1 (1%)** | **93 (73%)** |

So the metric already reports ≈1%, from 418 phantom rework units — it is not merely at risk from
the detector fix, it is broken now. And the failure clause is only stable while the detector is
blind: 62 of 313 observed runs are already failures, the missed invocations are ~2× that, and
nearly all of them are the red half of an ordinary TDD loop. Fixing detection under today's rules
would push both clauses further down, reporting a measurement improvement as a quality collapse.

Resolution (R-12, ADR-052): the factory metrics read `stage` records only — the rework clause as a
defect fix against ADR-035's own wording, the failure clause as a deliberate narrowing. R-12 lands
first so the re-baseline happens on a stable corpus, with the two clauses attributed separately.

## Divergence Summary

*Recorded: 2026-07-26 — Branch: tap-02-shared-runner-registry (tap-02 scope only)*

### Changed from plan

- **Wrapper normalisation for `npm run`, `yarn`, `pnpm` (tap-02, R-1):** the locked design
  unwrapped these as generic wrappers (`yarn vitest` → `vitest`). As built, their `test` forms
  are runner-table entries instead (`npm run test` → `npm test`, `yarn test`, `pnpm test`) and
  they are not unwrapped for arbitrary runners — `yarn vitest` and `npm run vitest` do not
  match. This is the conservative direction under the plan's own false-positive-avoidance rule
  (a missed run costs telemetry volume; a wrong match records a fabricated one); widening to
  generic unwrapping is a small registry change if telemetry later shows those shapes matter.

**Sequencing constraint.** R-1/R-2/R-3 touch the same module the R-4 split moves. Doing the
registry work first and the split second avoids rewriting the matcher inside a moving file.
R-12 precedes all of it for the reason above.

**Consistency with ADR-031.** ADR-031 credits `usage.py` for refusing to estimate what it cannot
measure — kimi cost is null rather than guessed. `_emit_test_run_from_verdict` violates that
principle in the same archive by writing `exit_code=0` and `result: success` literally for a run
it never observed. R-7 does not delete the record; it labels it, which is what the principle
actually demands.

**Deliberate scope choice.** R-4 and R-5 land together. An extension point with one
implementation is speculative; the second reader is what proves the seam, and this codebase
takes clean cuts over staged abstraction.

## Resolved Questions

Carried from the draft and settled during scope validation.

- **Should verdict-derived records keep being emitted once observed extraction works on both
  CLIs?** **Yes.** They uniquely carry `tests_total`/`tests_passed`/`tests_failed`, which no
  session log exposes. The fix is provenance marking plus aggregate exclusion (R-7, R-8), not
  deletion — and once both readers work, a verdict without an observed twin becomes a signal
  worth surfacing rather than noise.
- **How should the Claude transcript be located at emission time?** **By `session_id` from the
  result envelope**, analogous to kimi's resume-hint path, confirmed against the record's `cwd`.
  It falls back to null — never a guess — if the envelope was unparseable, which is also the
  R-11 failure mode.
- **Should the panel label pre-change records?** **Yes, as provenance-unknown, with no
  backfill.** Silently folding legacy records into the observed bucket would reintroduce the
  exact mixing R-8 removes.
- **Does fixing detection break the first-pass-merge metric?** **It would — and the metric is
  already broken.** Measuring the conflict found a rework-counting defect that pins the rate at
  ≈1%. Both clauses stop reading `test_run` records, and that lands first. See the
  metric-continuity note above; resolved as R-12 / ADR-052.

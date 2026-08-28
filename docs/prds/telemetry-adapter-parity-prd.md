# PRD: Telemetry Adapter Parity & Test-Run Fidelity

*Stage: synced*
*Next step: run `aet-ship`*

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
  step counts). That remains the parked `content/backlog/cfg-01-session-efficiency.md` idea; this PRD
  only builds the seam it would use.
- Changing validation **behaviour**. No freshness suppression, no stage-based skipping, no
  change to what gets run or when. `content/backlog/deterministic-qa-freshness-suppression.md`
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
- [x] A `make validate` run narrowed by `change_scope` to a subset of test paths is recorded
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
- [x] `mine_learnings` `full_suite_runs` counts are re-derived over a fixture containing both
      `full-suite` and newly `impact`-scoped `make validate` records, and the mined-learning
      output difference is documented rather than discovered later. (satisfies: R-13)
      — met over the real archive rather than a fixture; see the `tap-06` divergence below.

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

## Divergence Summary — tap-04

*Recorded: 2026-07-28 — Branches: tap-04-orchestrator-session-reference, tap-05-test-run-provenance*

Scoped to `tap-04` (R-6, R-9) and `tap-05` (R-7, R-8). Other requirements in this PRD are delivered by their own plans.

### tap-04 — Changed from plan

- **Task 1 / R-6 — the `adapter.name` branch moved down a layer rather than disappearing.**
  `CLIAdapter.resolve_session_ref` still does `if self.name == "kimi" / "claude"`. ADR-050's
  intent holds at the seam the plan named — the orchestrator asks and does not branch — but a
  third CLI is still an edit to an if-chain in `cli_adapter.py` rather than a registry entry,
  which is weaker than "the adapter resolves its own session reference" implies. The named test
  `test_session_reference_resolved_per_adapter_without_name_branch` asserts the spawn path
  delegates (an unknown adapter yields `None`); it does not assert, as the plan's coverage line
  describes, that "no `adapter.name ==` comparison remains on the resolution path".
- **Task 3 — `_emit_wire_test_runs` renamed to `_emit_session_test_runs` and gained an
  `agent_cli` parameter.** The `tap-03` dispatch keys on CLI name, so the emission site must pass
  it alongside the reference. The best-effort and null-reference contracts are unchanged.

### tap-04 — Not changed as planned

- **`src/aet/usage.py` was listed in Files to Modify — "kimi resume-hint resolver moves behind the
  adapter seam" — and was not touched.** `resolve_kimi_session_dir_from_output` stayed in
  `usage.py` and is now called from `cli_adapter.py`, which additionally reaches into that
  module's private surface (`_MAX_WIRE_LINE_CHARS`, `_find_result_element`, `TAIL_SCAN_BYTES`).
  The seam is honoured by call direction, not by relocation, and `cli_adapter` now depends on
  `usage` internals.

### tap-04 — Added (unplanned)

- **`src/aet/session_log_claude.py` gained `cwd_slug` and `transcript_path_for`** — not in Files
  to Modify. The plan assumed `tap-03` had left transcript-path construction available; it had
  not, so path derivation was added next to the reader that consumes it.
- **Post-merge correction (2026-07-28):** the original implementation stored `str(session_ref)`,
  a full local path, contrary to the plan's rejected alternative. It was corrected to store an
  adapter-independent identifier (the session id for both CLIs), with path resolution deferred to
  extraction time and documented in `docs/telemetry-guide.md`. The correction also added a guard
  around `resolve_session_ref` at the spawn site, resolved cwd through symlinks before slugging,
  and added the `session_identifier` field to the per-stage schema table in
  `docs/prds/aet-work-local-orchestrator-state-parallel-prd.md`.
- **Five tests beyond the nine the plan named**: the single-object `--output-format json` envelope
  (the shipped shape — all three planned Claude tests used a list envelope), log noise before the
  envelope, a missing transcript, an unknown adapter, and `_spawn_session` reference resolution.
  Three were added during QA and are already recorded in the plan's validation steps. The
  post-merge correction added a symlinked-worktree cwd test and an R-6 end-to-end integration
  test.

### tap-04 — Deferred

- **Task 7 (merge to main and verify integration)** — carried to `aet-ship`.

### tap-05 — Changed from plan

This branch was cut before `tap-04` merged, so it edits `_emit_wire_test_runs` under its old name
and appends this section where `tap-04` appended its own — both are integration work for
`aet-ship`, not divergences from intent.

### Changed from plan

- **`source` is validated against an enum, not merely required.** The plan and ADR-051 asked for a
  required argument "so a new emission site cannot omit it". `telemetry.test_run_record` also
  raises `ValueError` on any value outside `TEST_RUN_SOURCES = ("wire", "verdict")`, because a
  required argument alone still admits `source="wire "` or a future third emitter inventing a
  spelling that every reader's `== "wire"` check would silently drop into the unknown bucket.
- **Task 4 filters all of `mine_learnings`' `test_run` counting to observed, not only the two
  scope counts.** The plan named `full_suite_runs`/`impact_runs`. The `source != "wire"` guard sits
  at the top of the `test_run` branch, so `repeated_test_invocations` — derived from the same
  `task_full_suite_counts` — is observed-only too, and is labeled `(observed)` alongside the other
  two. Filtering the inputs but not the figure derived from them would have been incoherent.
- **The plan-level test aggregate is recomputed at the end of `buildPlans` rather than accumulated
  per record.** Provenance filtering cannot be expressed as a running sum over a mixed stream, so
  the per-record `p.testsAgg +=` block was removed and `claimedTestCounts`/`observedTestStats` run
  once over `p.tests`. Same figure shape, different construction.

### Added (unplanned)

- **`Th` now spreads its props (`e14dbbf`).** The provenance column headers and the "Tests
  (claimed)" headers carry `title` tooltips that explain which population the figure reads —
  `Th` dropped every prop but `children` and `className`, so the explanations rendered nowhere.
  Fixed with a regression test. This is a pre-existing panel defect the feature surfaced.
- **Two observed-side stats on the run and plan detail views** — "Observed pass rate" (both) and
  "Observed test time" (run). The plan asked for labeled aggregates; with counts declared as
  claimed, there was no observed figure on screen at all, and the split would have read as the
  removal of information rather than its separation.
- **Files beyond the planned list**: `CONTEXT.md` (the **Test Run** term still described the
  claimed record as `result: success` "true by construction" — corrected to the null `exit_code`
  this plan ships), `skills/aet-work/references/telemetry-log-schema.md` (where the `test_run`
  field table actually lives, so `source` is documented next to the fields it qualifies),
  `reports/2026-07-25-aet-performance-observability-review.md` (its published 80%/85% figures),
  and two fixture-bearing test files (`tests/telemetry/test_aet_retro.py`,
  `tests/track_record/test_track_record_metrics.py`).

### Recorded consequence

- **Every provenance-filtered surface reads `—` over the existing archive.** All 495 `test_run`
  records predate this change and carry no `source`, so ADR-051 decision 5 makes them
  provenance-unknown and excludes them. The 80% observed pass rate reproduced during validation is
  recoverable only by field-signature inference — the inference the decision refuses to make the
  forward contract. The panel's observed figures populate from records written after this change.
  Any longitudinal read spanning 2026-07-28 has to say so.

### Deferred

- **The orphan signal** (a claimed record with no observed twin) — ADR-051 decision 6, deliberately
  left out so this plan stays independent of the reader work. It becomes meaningful once both
  session-log readers land.
- **Task 7 (merge to main and verify integration)** — carried to `aet-ship`.
- **End-to-end validation** (a live `claude` session writing an observed `test_run` with a
  non-null duration and a traceable stage record) — needs a real orchestrated session; left for
  `aet-verify`. This is also the PRD acceptance criterion for R-6, which therefore remains
  unverified against live data.

## Divergence Summary — tap-06

*Recorded: 2026-07-28 — Branch: tap-06-targeted-validation-scope-observability*

Scoped to `tap-06` (R-10, R-13). Other requirements in this PRD are delivered by their own plans.

### Changed from plan

- **Task 2 / R-10 — the marker is trusted only when every marker in the output agrees.** The
  locked design said the classifier "reads the marker when present"; what shipped requires all
  markers in one command's output to name the same targets, and falls back to the heuristic on
  disagreement. Found in QA: `make validate`'s output contains its own pytest run, and pytest
  echoes captured stdout on failure — so a failing `change_scope` test reprints a marker naming
  *its fixture's* targets below the real one. Reading the last (or first) marker would have
  recorded a whole-suite run as `impact` precisely when tests were failing, understating suite
  cost at the worst moment. Repeated identical markers still classify; only disagreement falls
  back, since it is not resolvable from the output alone.
- **Task 3 / R-10 — the output field was added to both readers, not to the dispatch seam.** The
  plan listed `src/aet/session_log.py`; that file needed no change. The seam only dispatches, and
  the output travels inside the invocation dicts, so `wirelog.py` and `session_log_claude.py`
  each grew an `output` key. Claude's `tool_result` content is a string *or* a list of content
  blocks, so its reader joins the text blocks; the kimi wire carries a plain string.
- **Task 4 / R-13 — re-derived over the real archive instead of a fixture, and the count did not
  move.** The acceptance criterion asked for a fixture containing both `full-suite` and newly
  `impact`-scoped records. Building one would have measured the fixture, not the archive, so the
  re-derivation ran over all 497 archived `test_run` records: `full-suite` 331 / `impact` 152 /
  `unknown` 14, before and after. Nothing moved because no archived record carries the command's
  `output` — the input the marker path needs does not exist historically, which is the
  archive-immutability position ADR-051 takes, here reached by measurement rather than assumed.
  The obligation R-13 exists to discharge — document the shift rather than discover it later —
  is met: the plan's **R-13 Measurement** section records the zero delta, the 236 records (47%)
  that will shift going forward, and the `make test PYTEST_TARGETS=…` residual that stays
  `full-suite` because it never runs `change_scope`.

### Added (unplanned)

- **`docs/adr/049-validation-scope-from-change-set.md` gained a consequence.** The resolved
  target list is now a published output, not an internal decision, and that is a property of
  ADR-049's mechanism rather than of telemetry — so it is recorded where the mechanism is
  decided.
- **A property test pinning the no-output path to the pre-`tap-06` heuristic**
  (`test_omitting_output_is_identical_to_the_pre_tap06_heuristic`), plus tests separating a
  marker from a bare target list. The re-derivation asserted the same equivalence over all 497
  archived commands; the test keeps it true going forward.
- **`.coverage` untracked and gitignored.** It had been committed on `main`; unrelated to R-10,
  but it was dirtying every diff on this branch.

### Not changed as planned

- **`mine_learnings` was changed in its output description only, as planned — no counting logic
  moved.** Recorded here because the plan's re-baseline task could be read as promising a code
  change: the `full_suite_runs`/`impact_runs` counters are correct as written, and what was
  missing was the caveat that their split is not comparable across the `tap-06` boundary.

### Deferred

- **Task 6 (merge to main and verify integration)** — carried to `aet-ship`.
- **`make test PYTEST_TARGETS="…"` stays `full-suite`** (4 archived records). Genuinely narrowed,
  but `make test` never runs `change_scope`, so it emits no marker. Closing it means teaching the
  `test` target to echo a marker from shell — the untestable route the plan rejected.

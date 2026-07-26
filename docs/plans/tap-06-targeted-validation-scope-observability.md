---
id: tap-06-targeted-validation-scope-observability
size: M
blocked_by: [tap-02-shared-runner-registry]
pipeline: standard
status: queued
security_review: skipped
security_review_reason: reads a marker line from output the agent's own session log already contains and uses it to label a telemetry field; the marker is never executed, never interpolated into a command, and a malformed marker falls back to the current classification
docs_sync: required
docs_sync_reason: the `make` scope contract changes and the marker line becomes a documented interface between the Makefile and the classifier; docs/telemetry-guide.md and ADR-049's scope vocabulary are affected
---

# Plan: Make Targeted Validation Observable in Test-Run Scope

## Context

- PRD: `docs/prds/telemetry-adapter-parity-prd.md` (R-10, R-13)
- ADR: `docs/adr/049-validation-scope-from-change-set.md` — `vre-01` made `make validate` run a
  minimal target list; this plan makes that win visible in telemetry.
- Measured motivation: `reports/2026-07-25-aet-performance-observability-review.md` — every
  `make` invocation classifies `full-suite`, so the `vre-01` change is invisible in the archive.
- Verified current behaviour (2026-07-26): `telemetry._test_runner_args`
  (`src/aet/telemetry.py:77-79`) returns `[]` for any `make` invocation whose targets include
  `test` or `validate`, and `classify_test_scope` (`:40`) then finds no narrowing argument and
  returns `full-suite`. Its docstring is explicit: "make targets are never paths in v1."
- `make validate` (`Makefile:98-110`) already runs `python -m aet.change_scope --explain` and
  then `make test PYTEST_TARGETS="$$targets"`. The sub-make is a child process the agent's shell
  tool never sees, so the session log records only the outer `make validate` — the resolved
  targets exist only in the command's **output**.
- `change_scope.main` (`src/aet/change_scope.py:190-201`) prints human prose under `--explain`:
  `→ targeted tests: tests/foo tests/bar (changed paths: N)` or `→ full suite (changed paths: N)`.
- Consumer at risk: `mine_learnings` (`src/aet/cli/mine_learnings.py:239-244`) counts
  `full_suite_runs` and `impact_runs` by `scope`, and feeds `task_full_suite_counts`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
  — the `make` classification is a defect, but the fix requires a new marker interface between
  the Makefile and the classifier, which a targeted fix cannot deliver.

## Locked design

- **A stable machine-readable marker, not scraped prose.** `change_scope` emits one marker line
  alongside its human `--explain` output, carrying the resolved targets. The human line stays for
  humans; the marker is the contract. Parsing the prose would make an operator-facing message
  load-bearing.
- **The classifier takes optional command output.** `classify_test_scope(command, output=None)`
  reads the marker when present and falls back to the current command-string heuristic when it is
  not. The pure-heuristic path — auditable, environment-independent, as its docstring promises —
  survives untouched for every non-`make` command and for `make` runs with no marker.
- **The marker is data, never code.** It is matched against the resolved-target grammar and used
  only to pick a scope label. A malformed or absent marker falls back; nothing from it is
  executed, interpolated, or path-resolved.
- **Session readers pass result output to the classifier.** Both readers already capture the
  `tool_result` content (the kimi reader parses it for the exit-code trailer,
  `src/aet/wirelog.py:42`); this exposes it to the emission site.
- **`full-suite` still means the full suite.** A `make validate` that resolved to `tests/` is
  `full-suite`; one narrowed to a subset is `impact`; a `make` run with no marker stays
  `full-suite`, the current conservative answer, matching ADR-049's fail-toward-more-tests bias.
- **R-13 is a measurement obligation, not a code change.** Before and after, `full_suite_runs` and
  `impact_runs` are re-derived over the existing archive and the difference is documented in the
  merge notes, so the mined-learning shift is recorded rather than discovered later.

## Rejected Alternatives

- **Parse the `--explain` prose** — rejected: it makes a human-facing message a machine contract
  and breaks on any copy edit.
- **Have the orchestrator call `change_scope` itself at emission time** — rejected: the scope is a
  property of the worktree's diff *when the agent ran the command*, which the orchestrator cannot
  reconstruct after the fact.
- **Have `make` echo the expanded `PYTEST_TARGETS` and match on the echo** — rejected: it puts
  the contract in shell where it cannot be tested, and `change_scope` already computes the value.
- **Classify `make` as `unknown` instead of `full-suite` when there is no marker** — rejected: it
  would reclassify every historical record into a bucket no consumer handles, and `full-suite` is
  the safe answer under ADR-049's bias.
- **Re-baseline `mine_learnings` by adjusting historical records** — rejected: records are
  immutable, and ADR-051 already rejects rewriting archived telemetry to fit a new definition.

## Task List

1. Emit a stable machine-readable resolved-targets marker from `change_scope`, alongside the
   existing human `--explain` line — S (traces: R-10)
2. Extend `classify_test_scope` with optional command output: parse the marker, classify by the
   resolved targets, fall back to the current heuristic when absent or malformed — M
   (traces: R-10)
3. Pass `tool_result` output through the session-reader interface to the emission site so the
   classifier receives it — S (traces: R-10)
4. Re-derive `full_suite_runs`/`impact_runs` over the existing archive before and after; document
   the shift in the merge notes and in `mine_learnings`' output description — S (traces: R-13)
5. Tests (see Validation Steps) — M (traces: R-10, R-13)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: emitting the marker, reading it, and re-baselining its one downstream consumer
  are one change — a marker nothing reads is dead output, and a reclassification whose consumer
  shifts silently is the failure R-13 exists to prevent. Depends only on `tap-02` for the shared
  registry the `make` branch now lives in.

## Files to Modify

- `src/aet/change_scope.py`
- `src/aet/telemetry.py`
- `src/aet/session_log.py` (pass result output through the invocation shape)
- `src/aet/cli/orchestrator.py`
- `src/aet/cli/mine_learnings.py` (output description only)
- `tests/test_change_scope.py`
- `tests/telemetry/test_telemetry.py`
- `tests/session_log/test_session_log_dispatch.py`
- `docs/telemetry-guide.md`

## Validation Steps

- [ ] `make validate` passes
- [ ] Coverage:
  - `test_change_scope_emits_resolved_targets_marker` (unit)
  - `test_marker_absent_for_prose_only_change` (unit)
  - `test_classify_scope_reads_marker_and_returns_impact_for_narrowed_targets` (unit)
  - `test_classify_scope_returns_full_suite_for_marker_naming_suite_root` (unit)
  - `test_classify_scope_falls_back_to_heuristic_when_marker_absent` (unit)
  - `test_classify_scope_falls_back_when_marker_malformed` (unit)
  - `test_classify_scope_unchanged_for_non_make_commands` (unit) — the heuristic path is
    untouched
  - `test_session_reader_exposes_result_output_to_emission_site` (unit)
- [ ] R-trace coverage: R-10 by tasks 1, 2, 3, 5; R-13 by tasks 4, 5; no unknown R-ids
- [ ] For the new marker parsing in `telemetry.py`, tests above name the coverage
- [ ] End-to-end: a `make validate` narrowed by `change_scope` records `scope: "impact"`; an
      unnarrowed run still records `full-suite`
- [ ] `full_suite_runs`/`impact_runs` re-derived over the existing archive, before/after figures
      recorded in the merge notes
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; `make` invocations classify `full-suite` again and the marker line stops
being emitted. Records written with `scope: "impact"` stay valid — `impact` is an existing scope
value — so the archive needs no migration, and the `full_suite_runs` shift documented in task 4
identifies exactly which records are affected in either direction.

---

*Stage: plan-approved*

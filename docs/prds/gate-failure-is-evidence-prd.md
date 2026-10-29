---
id: gate-failure-is-evidence
status: accepted
---

# PRD: A Gate Failure Is Evidence, and Retries Are Bounded

## Overview

A checking stage can fail after its agent session exits 0: the gate finds a
failing, missing or malformed verdict. That failure records no signature, so
triage has no evidence, requeues by default, and the circuit breaker never
counts it. No attempt cap exists. A task can loop until an operator stops the
run. This PRD makes a gate failure countable evidence, caps attempts per run,
stops the review lenses from blocking every verdict, and classifies two more
transient errors. ADR-084 records the decision.

## Intake Triage

Enhancement that closes three defects shown in v1.23.0 code. The fix changes
failure policy (gate failure class, attempt cap, lens behavior), which needs a
PRD and an ADR rather than a targeted bug fix. Work class: `critical`, because
the change decides when a task is requeued, quarantined or stopped.

## Evidence

From `content/backlog/client-run-mining-report-2026-10-28.md`, problems 1, 4
and 14, checked against v1.23.0 (`3d626d11`):

- **Unbounded requeue.** In one client project, five tasks were requeued 112,
  41, 30, 24 and 12 times after gate failures (2026-10-05 to 10-27): 230
  attempts, about $107 and 6.4 hours. Each cycle logged `❌ Gate fail-closed`
  and `🔄 <id> requeued`; 126 lines logged `Triage for <id> skipped:
  insufficient evidence (no tail or signature)`. Four loops ended only on
  SIGTERM.
- **Cause.** `_require_passing_verdict` (`src/aet/cli/orchestrator.py`)
  returns False without calling `_record_failure_on_task`, which runs only
  after a non-zero session exit. `_finalize_task` finds no new entry,
  `triage.has_sufficient_evidence` is False, and `_TRIAGE_DEFAULT_ACTIONS`
  maps the default `environment` class to requeue.
  `breaker.should_quarantine_task` counts only signature entries.
- **Lens refusal.** `_submit` (`src/aet/cli/gate.py`) runs the boundary and
  identity lenses for `--stage review` before writing; a tripped lens returns
  an error for `pass` and `fail` alike, so no verdict file exists. The same
  project logged 93 `missing review verdict ... attempting one recovery
  session` lines. The lenses use `telemetry.resolve_repo_root()`
  (`AET_REPO_ROOT`), while `_verdict_tree_root` uses `AET_WORKTREE`.
- **Transient errors.** Through `failure.classify`, a bare
  `API Error: 529 Overloaded` and "computer went to sleep mid-response" give
  `flaky` and are requeued at once. Two client projects had 94 and 20
  immediate requeues on HTTP 429 before ADR-065.

## Goals

- No task loops without limit after a gate failure.
- Triage receives evidence for every gate failure.
- A review that trips a lens leaves a verdict.

## Non-Goals

- Run-summary and stage telemetry that count a requeue as no failure
  (backlog package 4).
- Backoff or delayed requeue for transient errors.
- A configurable attempt cap.
- Changes to the lenses' own rules.

## Requirements

- **R-1**: When `_require_passing_verdict` decides a gate failure, it records
  a failure entry on the task before it returns False, through
  `_record_failure_on_task`.
- **R-2**: The entry's class follows the verdict state: `fail` gives `design`;
  missing, malformed or invalid gives `environment`. Both are countable.
- **R-3**: The entry's signature is computed from the stage and the fixed key
  `gate:<kind>:<state>`. Three gate failures of one kind and state on one task
  produce one signature, whatever the verdict detail.
- **R-4**: The entry's tail preview holds the gate key, the gate detail line,
  and the verdict summary when one exists, so `triage.has_sufficient_evidence`
  is True for a gate failure.
- **R-5**: A task whose third identical gate failure is recorded is
  quarantined by the existing per-task breaker.
- **R-6**: A task that fails five times within one run is quarantined,
  whatever its signatures or classes. `throttled` and `canceled` outcomes do
  not count toward the five.
- **R-7**: A quarantine by the attempt cap prints the cap and the count, and
  the triage telemetry record carries the reason `attempt_cap`.
- **R-8**: When a review lens trips, `aet gate submit --stage review` writes a
  `fail` verdict that carries the lens findings and exits non-zero with the
  remedy. This holds for `--verdict pass` and `--verdict fail`.
- **R-9**: A later `aet gate submit --stage review --verdict pass` whose lenses
  do not trip replaces that fail verdict.
- **R-10**: The review lenses take their repository root and changed paths from
  the tree the verdict attests to (`AET_WORKTREE` when set).
- **R-11**: `failure.classify` returns `throttled` for a 529 with an
  `API Error` or `api_error_status` qualifier and for `529 Overloaded`. A bare
  `529` with no qualifier is not matched.
- **R-12**: `failure.classify` returns `environment` for "computer went to
  sleep mid-response".
- **R-13**: `CONTEXT.md` lists all six failure classes and describes the
  attempt cap with the **Circuit Breaker**; ADR-030 and ADR-065 name ADR-084 as
  an amendment; the `aet-drive` skill names the attempt cap under Residual
  Failures.
- **R-14**: Existing breaker, throttle and verdict-recovery tests pass
  unchanged, except where they assert the old gate-failure behavior.

## User Stories

- As an operator running a night shift, I want a task that keeps failing its
  gate to stop after a few attempts, so that one task cannot burn the run.
  (satisfies: R-1, R-2, R-3, R-5, R-6, R-7)
- As an operator, I want triage to see why a gate failed, so that it chooses
  between requeue and quarantine on evidence. (satisfies: R-4)
- As a reviewer agent, I want a tripped lens to leave a fail verdict with its
  findings, so that the gate and the next attempt know what to fix.
  (satisfies: R-8, R-9, R-10)
- As an operator, I want provider overload and host sleep classified
  correctly, so that they neither loop nor hide as flakes. (satisfies: R-11,
  R-12)

## Acceptance Criteria

- [ ] A task whose QA verdict is `fail` three times in one run is quarantined
  after the third attempt, and its three entries share one signature.
  (satisfies: R-1, R-2, R-3, R-5)
- [ ] After a gate failure, the run log shows a triage decision, not
  `Triage ... skipped: insufficient evidence`. (satisfies: R-4)
- [ ] A task that fails five times in one run with five different signatures
  is quarantined, and the log names the cap. (satisfies: R-6, R-7)
- [ ] A throttled failure followed by four other failures does not quarantine
  the task by the cap. (satisfies: R-6)
- [ ] With a tripped boundary lens, `aet gate submit --stage review --verdict
  pass` exits non-zero and a `fail` verdict file with the lens findings exists.
  (satisfies: R-8)
- [ ] After the cause is fixed, `--verdict pass` writes a passing verdict.
  (satisfies: R-9)
- [ ] With `AET_REPO_ROOT` and `AET_WORKTREE` set to different trees, the
  lenses judge the files changed in `AET_WORKTREE`. (satisfies: R-10)
- [ ] `failure.classify` returns `throttled` for `API Error: 529 Overloaded`
  and `environment` for the host-sleep message; `test 529 passed` stays
  unmatched. (satisfies: R-11, R-12)
- [ ] `aet docs lint` passes and `CONTEXT.md` lists six failure classes.
  (satisfies: R-13)
- [ ] `make validate` passes. (satisfies: R-14)

## Technical Notes

- `_record_failure_on_task` computes the signature from its `tail` argument
  and stores `tail[-1500:]` as the preview. R-3 and R-4 need the two apart:
  an optional `preview` argument, or a signature key argument.
- `failure.signature` uses the most specific error line of the tail
  (`_extract_error_key`), so a tail that holds the verdict detail would give a
  different signature per attempt.
- `_require_passing_verdict` already receives `task` and `backend` at both
  call sites in `process_task`.
- The attempt count is run-local: a counter per task id in `run_batch`,
  updated in the reap path that calls `_finalize_task`.
- `_verdict_tree_root` (`src/aet/cli/gate.py`) already resolves the worktree.
  `change_scope.changed_paths` reads the current directory.
- The identity lens reads `<root>/docs/plans/<task-id>.md`. The root checkout
  keeps plans under `docs/plans/active/`, so the lens never finds the
  declarations there; the worktree holds the rendered plan at that path. R-10
  also restores the declaration lookup.

## Risks

- **Stricter outcome for a real `fail`.** `design` defaults to quarantine when
  the triage session errors. A task that used to retry until it passed now
  stops. Accepted: ADR-030 routes a design failure to a human.
- **Signature collision across verdict reasons.** All `fail` verdicts of one
  kind share a signature, so three different QA failures quarantine. Accepted:
  three failed QA attempts in one run need a human either way.
- **Lens root change.** Lenses that read the worktree may trip on reviews that
  passed before, because they now see the real change.

## Open Questions

- None.

## Scope Validation

Checked on 2026-10-28 against `CONTEXT.md`, ADR-023, ADR-030, ADR-065,
ADR-069, ADR-071 and ADR-073, and against the v1.23.0 code:

- ADR-084 amends ADR-030 decisions 2 and 3 and extends ADR-065 decision 1; it
  contradicts no other decision. `gfe-02` records both amendments.
- `CONTEXT.md` **Failure Class** lists five classes; `throttled` (ADR-065) is
  missing. `gfe-02` corrects it.
- The identity-lens plan lookup finding above was added to `gfe-03`.
- All three plans use `pipeline: standard`, which suits `critical` work.

## Delivery

| Plan | Requirements | Blocked by |
| --- | --- | --- |
| `gfe-01-gate-failure-is-evidence` | R-1 to R-5, R-14 | — |
| `gfe-02-bounded-retries` | R-6, R-7, R-11 to R-14 | `gfe-01` |
| `gfe-03-lens-trip-writes-fail-verdict` | R-8 to R-10, R-14 | — |

## Divergence Summary

*Recorded: 2026-10-28 — Branch: gfe-01-gate-failure-is-evidence*

### Changed from plan

- None.

### Added (unplanned)

- `src/aet/perf_report.py`: Used `timezone.utc` instead of `datetime.UTC` for Python 3.10 compatibility.

### Deferred

- None.

*Stage: synced*
*Next step: run `aet-ship`*

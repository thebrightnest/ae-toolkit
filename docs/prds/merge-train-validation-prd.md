---
id: merge-train-validation
status: accepted
branch: feat/merge-train-validation
pr_title: "feat(integration): merge train with one integrate path, verdict-aware gate, and ship cleanup"
---

# PRD: Merge Train Validation — One Integrate Path, Verdict-Aware Gates, Ship Cleanup

## Overview

Every project running AET pays for its full validation suite several times per
task, and under parallel `aet run` it pays for it **serially**:

1. aet-qa runs the full suite and writes a `qa` verdict stamped with
   `tree_hash` (ADR-025).
2. On completion, `_integrate_completed_task` (`src/aet/cli/orchestrator.py`)
   takes `integration_lock`, rebases onto the integration tip, and runs the full
   `make validate` again (`_validate_after_rebase`) —
   **inside the lock**, so N parallel tasks queue behind N sequential suite runs.
3. Residual `awaiting_merge` tasks are merged by the aet-drive agent through
   `aet ship merge`, whose gate (`_run_gate` in `src/aet/cli/ship.py`) runs the
   full suite a third time — outside the lock, with a different command variable
   (`AET_SHIP_TEST_CMD` vs `AET_INTEGRATION_VALIDATE_CMD`) and a different merge
   strategy (`--no-ff` vs squash).
4. `aet ship open-epic` runs the suite again on the epic branch, even when that
   exact tree was just validated.

No integration path consults the QA verdict, although `evidence.validation_freshness`
exists for exactly that question. The stated reason (ADR-070 decision 2: the
reports archive is "per-machine") does not hold: a task is always run, integrated
and shipped on the one machine that holds its verdicts.

The ship surface has also accumulated leftovers: four merge implementations,
a test-only argparse dispatch duplicating the live Typer app, a coverage command
whose result is discarded, a stacked-branch guard that can never fire, and skill
docs that describe behaviour the code does not have.

This PRD replaces per-task post-rebase validation with a **merge train**: tasks
are checked against their own QA verdict, squash-merged under the lock onto a
local staging ref without running the suite, and the suite runs **once per
batch** on the staging tip. Green fast-forwards the integration branch and marks
the batch `merged`; red bisects deterministically and ejects the culprit. All
integration entry points collapse into one `integrate()` path, configured by
project config keys instead of environment variables.

**Intake Triage Guard:** Confirmed enhancement (simplification and throughput).
Not a reproducible defect — current behaviour is correct but redundant.

## Goals

- The full validation suite runs once per **batch** of integrated tasks, not once
  per task, and never while `integration_lock` is held.
- A task whose tree is identical to the tree its QA verdict attests to is
  never re-validated before staging.
- The integration branch (trunk in `pr-per-task` mode) only ever advances to a
  tree that passed `validate_command`.
- Exactly one code path merges a task into its integration target.
- Every "does this run tests?" decision is computed in code from recorded
  verdicts and the change set; none is left to agent prose.
- `src/aet/cli/ship.py` loses its dead and duplicate code paths.

## Non-Goals

- Prompt-level freshness for review/cso/sync stages (ADR-025) — unchanged.
- The desk's PR-based merge (`desk.py` `gh pr merge`) — a human PR path, unchanged.
- Language- or runner-specific test selection in downstream projects. Scope
  narrowing stays whatever `validate_command` does internally.
- Remote/shared merge queues or coordination between operators (ADR-045 scope
  boundary: one operator, one queue).
- Changing aet-qa's own full-suite run.

## Requirements

- **R-1**: Project config accepts `validate_command` (default `make validate`)
  and optional `lint_command`, resolved through the ADR-048 two-layer chain and
  writable via `aet configure`. `AET_SHIP_TEST_CMD`,
  `AET_INTEGRATION_VALIDATE_CMD` and `AET_SHIP_COVERAGE_CMD` are no longer read.
- **R-2**: Before a task is staged, code computes `validation_freshness(task, "qa")`
  on the task worktree: `SKIP` runs nothing; `LINT_ONLY` runs `lint_command`, or
  `validate_command` when unset; `RUN` (including a missing or failing verdict)
  runs `validate_command`. A failure leaves the task `awaiting_merge` with
  diagnostics. This check never runs under `integration_lock`.
- **R-3**: A single `integrate(task)` function performs, under
  `integration_lock`: fetch, rebase onto the train tip, conflict check, release
  guard, monolithic-commit guard, and a squash-merge onto the local staging ref
  `refs/aet/train/<integration-branch>`. It runs no test suite. Conflicts and
  guard failures leave the task `awaiting_merge` with diagnostics.
- **R-4**: `aet run` integration, `aet ship merge`, and policy auto-merge
  (`track_record.perform_auto_merge`) all call `integrate()`; no other code path
  merges a task into its integration target.
- **R-5**: A staged task stays `awaiting_merge` and its record carries a train
  marker (staging commit, batch position). No new task state is introduced.
- **R-6**: The train flushes when: (a) `aet run` has no in-progress or ready work
  left; (b) a task is otherwise ready but at least one blocker is staged;
  (c) `aet ship open-epic` runs; (d) `aet ship merge` is invoked. A flush runs
  `validate_command` once in a temporary worktree at a snapshot of the staging tip.
- **R-7**: On a green flush the integration branch fast-forwards to the snapshot,
  is pushed, every task in the snapshot transitions to `merged` with its staged
  commit as merge evidence (ADR-064), and a batch verdict stamped with the
  snapshot's `tree_hash` is recorded. Tasks staged after the snapshot remain
  staged for the next flush.
- **R-8**: On a red flush, a deterministic prefix bisect replays the batch onto
  the integration tip in a temporary worktree to find the first failing task.
  The culprit loses its train marker and stays `awaiting_merge` with the failing
  output as diagnostics; the remaining tasks are re-stacked onto the integration
  tip and the train flushes again. A task that no longer re-stacks cleanly is
  ejected with conflict diagnostics.
- **R-9**: `aet ship open-epic` and `aet ship gate` skip `validate_command` when
  a passing batch verdict or the task's `qa` verdict covers the identical tree
  (`SKIP`), and apply the R-2 tiers otherwise.
- **R-10**: ADR-070 decision 2 is superseded: ship-time gates consume recorded
  verdicts. A new ADR records the merge train and the single integrate path.
- **R-11**: `src/aet/cli/ship.py` no longer contains: the argparse `build_parser`/`parse_args`/
  `main` dispatch, the `record-merge` alias, the unreachable stacked-branch guard
  in `cmd_merge`, the duplicate `prepare_worktree_dependencies` call, unread
  `GateResult` fields, duplicate task-record loaders, and the hardcoded queue
  path / `branch=task_id` passed to `record_merge`. Tests reach ship only
  through the Typer app.
- **R-12**: aet-ship and aet-drive skill docs and `docs/CLI.md` describe the
  train, the flush triggers, the config keys, and the gate's actual evidence
  checks; the invalid `aet ship merge <epic-branch>` example is gone.

## User Stories

- As an operator running `aet run --max-jobs 4`, I want finished tasks to
  integrate without each one waiting for a full suite under the lock, so parallel
  work stays parallel through integration. (satisfies: R-3, R-6, R-7)
- As an operator, I want trunk (or the epic integration branch) to never advance
  to an untested tree, so the absence of CI is still safe. (satisfies: R-6, R-7, R-8)
- As an operator, I want one broken task in a batch to be ejected, not to block
  its batch-mates, so a single failure costs one task, not a run. (satisfies: R-8)
- As a dependent task's operator, I want my task to start in the same run as its
  blocker, so chains still progress under the train. (satisfies: R-6)
- As a project adopter, I want to set my validation command once in config, so
  `aet run` and `aet ship` cannot disagree about what "validated" means. (satisfies: R-1)
- As an aet-drive agent, I want `aet ship merge` to be the same mechanism as
  `aet run` integration, so residual merges behave identically. (satisfies: R-4)
- As a maintainer, I want ship.py free of dead dispatch and guards, so the next
  change does not have to reason about paths that never run. (satisfies: R-11, R-12)

## Acceptance Criteria

- [x] With `validate_command` set in `.agents/aet-config.json`, `aet run` and
      `aet ship merge` invoke that command; setting `AET_SHIP_TEST_CMD` has no
      effect. (satisfies: R-1)
- [x] A task whose worktree tree equals its passing QA verdict's `tree_hash` is
      staged without any validation command running; one with a post-QA code
      edit runs `validate_command` before staging. (satisfies: R-2)
- [x] While one task is staging, `integration_lock` is held for seconds, not for
      a suite run: no validation subprocess starts while the lock is held. (satisfies: R-3)
- [x] `git grep` finds no `merge --no-ff`/`merge --squash` of a task branch
      outside `integrate()`. (satisfies: R-4)
- [x] Three independent tasks completing during one run produce one
      `validate_command` invocation at end of run and three `merged` tasks. (satisfies: R-6, R-7)
- [x] Task B blocked by staged task A starts in the same run after a flush. (satisfies: R-6)
- [x] The integration branch ref is only ever moved to a commit that has a
      passing batch verdict. (satisfies: R-7)
- [x] A batch of four where task 3 breaks the suite ends with tasks 1, 2, 4
      `merged` and task 3 `awaiting_merge` with the failing output. (satisfies: R-8)
- [x] `aet ship open-epic` on a tip just validated by a flush runs no suite. (satisfies: R-9)
- [x] An ADR supersedes ADR-070 decision 2 and records the train. (satisfies: R-10)
- [x] `aet ship record-merge` no longer exists; `src/aet/cli/ship.py` has no `argparse`
      parser; the ship test suite runs through Typer's `CliRunner`. (satisfies: R-11)
- [x] aet-ship SKILL.md lists the gate's real checks and no epic-branch merge
      example; `aet docs generate` output matches. (satisfies: R-12)

## Technical Notes

- **Content hash, not commit SHA.** `verifier.working_tree_hash` hashes file
  content through a throwaway index, so a rebase that pulls in nothing keeps the
  hash and freshness returns `SKIP` (R-2, R-9).
- **Lock scope.** `integration_lock` (`src/aet/integration_lock.py`) covers only
  the staging-ref mutation and record updates. Flush takes the lock only to
  snapshot the staging tip and, on green, to fast-forward and transition tasks;
  the suite runs between those two critical sections.
- **Local staging ref.** `refs/aet/train/<branch>` is never pushed (ADR-045
  Scenario B: no extra artefacts in a shared repo). It is rebuildable from the
  task records' train markers, so losing it is recoverable.
- **Forward-only state (ADR-011).** `awaiting_merge → merged` remains the only
  exit. Ejection removes a train marker; it does not transition state.
- **Fail-closed (ADR-029).** Any flush error that is not a red suite (git
  failure, missing worktree, push rejection) halts integration for the run and
  leaves all staged tasks `awaiting_merge` — never `merged`.
- **Dependency safety.** Trigger R-6(b) means dependents only ever start from a
  validated integration tip, so bisect ejection never needs to cascade.
- **Bisect cost.** Prefix bisect on a batch of n is ⌈log₂ n⌉ suite runs. The cost
  is paid only on red; green batches pay one run.
- **Leftovers found in research** (2026-10-12): argparse dispatch reachable only
  from tests (the former build_parser, parse_args, and main helpers in the ship CLI module); `record-merge` routes to the same handler as
  `close`; the stacked guard in `cmd_merge` is unreachable because `cmd_merge`
  always sets `args.base`; `AET_SHIP_COVERAGE_CMD` output discarded
  in `_run_gate`; `prepare_worktree_dependencies` called twice; `GateResult.dry_run`
  unread; `_load_task_record`/`_resolve_task_record` duplicate; `record_merge`
  gets a hardcoded queue and `branch=task_id` in `cmd_merge`;
  `track_record.perform_auto_merge` checks out `main` in the repo root.
- **Related ADRs:** 011, 025, 029, 045, 048, 064, 070 (decision 2 superseded).

## Open Questions

- None blocking. Batch-size cap is deliberately absent: trigger R-6(b) bounds
  batch growth whenever dependents exist; independent work batches to end of run
  by design.

## Risks

- **Late failure detection.** A red suite surfaces at end of run instead of at
  integration. Mitigated by bisect ejection and the R-2 per-task check.
- **Semantic conflicts between batch-mates** are now caught only at flush — this
  is the intended trade, and bisect isolates them.
- **Broad blast radius in `ship.py` and the orchestrator.** Mitigated by landing
  the cleanup first (smaller surface), then the gate, then the train.
- **The train is a new invariant** (integration branch only moves to validated
  trees); a bug in fast-forward or bisect could strand tasks. Mitigated by
  fail-closed handling and rebuildable staging refs.

*Stage: synced*
*Next step: run `aet-ship`*

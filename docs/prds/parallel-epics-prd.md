---
id: parallel-epics
status: accepted
---

# PRD: A Task's PRD Names Its Epic, and Epics Run in Parallel

## Overview

In `single-pr` mode, `aet run` integrates every task into one epic branch. A
queue that holds tasks from several PRDs therefore cannot run them in parallel
without merging unrelated work into one branch. This PRD makes each task's PRD
name its epic branch, so one run drives several epics at once, one integration
branch per epic. ADR-083 records the decision.

Four defects cause the current behavior:

1. `resolve_integration_branch_for_task` (`src/aet/branch_ref.py`) checks the
   envelope active epic before the PRD filename. When an active epic is set,
   every task without a declared `branch` resolves to that one epic.
2. `run_batch` (`src/aet/cli/orchestrator.py`) resolves one base branch per
   run and passes it to `create_worktree` (`src/aet/worktree.py`) for every
   task. The integration branch is stamped per task, but the worktree base is
   not.
3. The epic mismatch guard in `run_batch` sets `stop_spawn`. One mismatched
   task halts the whole batch.
4. `cmd_open_epic` (`src/aet/cli/ship.py`) and `aet epic show` read one active
   epic from the queue envelope.

The merge train already flushes per branch (`flush`, `src/aet/train.py`), and
the integration step already runs under one local lock (ADR-045 §5).

### Observed case

On 2026-10-27 the `dhl-agentic-rac` queue held 5 ready tasks from 5 PRDs:
`chatup`, `cite`, `conv`, `levels` and `tel`. The active epic was
`feat/conversation-store`. None of the 5 PRDs declares `branch`. All 5 tasks
resolved to `feat/conversation-store`. The driving session ran only
`conv-01b-chatbot-on-the-store`, by hand with `aet run-one --base`, to keep
the other 4 PRDs out of that branch.

## Intake Triage

Enhancement. Each defect above follows from ADR-076 decision 2, "one active
epic at a time", which is designed behavior. Work class: `critical`, because
the change selects the branch that task commits integrate into.

## Goals

- One `aet run` executes ready tasks from several epics concurrently, up to
  `--max-jobs`.
- Each task integrates into the epic branch of its own PRD, with no operator
  step per epic.
- A problem with one task or one epic branch does not stop work on the other
  epics.

## Non-Goals

- `pr-per-task` mode. Its behavior does not change.
- A lock per integration branch. The single integration lock stays.
- Host-repository commit hooks, such as a PR-size gate that measures an epic
  task against trunk. They belong to the host repository, not to AET.
- Fair scheduling between epics. `--max-jobs` stays one limit for the batch.

## Requirements

- **R-1**: In `single-pr` mode, a task's integration branch resolves in this
  order: CLI `--base`, `AET_WORK_BASE_BRANCH`, task stamp, PRD frontmatter
  `branch`, branch derived from the PRD filename, config
  `integration_branch`, trunk. The envelope active epic is not a step.
- **R-2**: The derived branch is `feat/` plus the PRD filename stem with a
  trailing `-prd` removed. `docs/prds/conversation-store-prd.md` derives
  `feat/conversation-store`.
- **R-3**: Every worktree that `aet run` creates is based on the live tip of
  that task's integration branch, resolved by `resolve_base_ref`. This applies
  to the batch path and to the single-task path.
- **R-4**: When a task's integration branch does not exist locally or on the
  remote, the run creates it locally from the trunk tip before it cuts the
  first worktree for it. The run does not push it (ADR-045 §4).
- **R-5**: The run checks base hygiene once for each distinct integration
  branch, before the first spawn on that branch. A branch that fails the check
  skips its tasks. Tasks on other branches continue.
- **R-6**: A task whose stamp differs from its resolved branch is skipped for
  the rest of the run. Its state does not change. Other tasks continue.
- **R-7**: A task whose blocker resolves to a different integration branch is
  not spawned. The run reports it as a cross-epic dependency and names both
  branches.
- **R-8**: Tasks on different integration branches run concurrently up to
  `--max-jobs`. Their integration steps stay serialized under the integration
  lock.
- **R-9**: The run summary lists each skipped task with its reason and remedy.
  The run exits non-zero when it skipped at least one task.
- **R-10**: The run banner prints each integration branch in the batch with its
  provenance, in place of the single `Integration:` line.
- **R-11**: `aet epic set` and `aet epic clear` are removed, with no alias
  (ADR-039). An `epic` key found in the queue envelope is ignored, named in one
  warning line, and dropped on the next envelope write.
- **R-12**: `aet epic list` replaces `aet epic show`. It prints each integration
  branch that a queued task resolves to, with provenance, task counts by state,
  and PR title.
- **R-13**: `aet ship open-epic <branch>` takes the branch as an argument. The
  argument is optional only when the queue resolves to exactly one integration
  branch.
- **R-14**: `aet ship open-epic` finds the PRDs whose resolved branch equals
  the argument by reading `docs/prds/`. The PR title is the PRD frontmatter
  `pr_title`, else the PRD H1 without its `PRD: ` prefix. The PR body file is
  the PRD frontmatter `pr_body_file` when declared. Two PRDs on one branch
  with different `pr_title` values make the command refuse and name both.
- **R-15**: The `aet-drive` and `aet-ship` skills, `docs/CONVENTIONS.md` and
  `docs/CLI.md` describe one epic per PRD and contain no `aet epic set`.
- **R-16**: In `pr-per-task` mode, branch resolution, worktree base and run
  output are unchanged. A regression test covers this.

## User Stories

- As an operator with tasks from several PRDs in the queue, I want one
  `/aet-drive` to run them in parallel, each into its own epic branch, so that
  independent epics finish in the time of the longest one. (satisfies: R-1,
  R-2, R-3, R-4, R-8, R-10)
- As an operator, I want a bad task or a bad epic branch to stop only its own
  work, so that one problem does not idle the whole shift. (satisfies: R-5,
  R-6, R-7, R-9)
- As an operator, I want to see and ship each epic by its branch name, so that
  I open one PR per epic without declaring each epic first. (satisfies: R-11,
  R-12, R-13, R-14, R-15)
- As an operator in `pr-per-task` mode, I want nothing to change. (satisfies:
  R-16)

## Acceptance Criteria

- [ ] A queue with ready tasks from PRDs `a-prd.md` and `b-prd.md`, neither
  declaring `branch`, runs both tasks concurrently. Task A integrates into
  `feat/a` and task B into `feat/b`. (satisfies: R-1, R-2, R-8)
- [ ] A PRD that declares `branch: feat/x` sends its tasks to `feat/x`, not to
  the derived name. (satisfies: R-1)
- [ ] The worktree for task B contains the commits on `feat/b` and none of the
  commits on `feat/a`. (satisfies: R-3)
- [ ] When `feat/b` does not exist, the run creates it from the trunk tip, and
  `git ls-remote origin feat/b` stays empty after the run. (satisfies: R-4)
- [ ] When `feat/a` fails base hygiene, task B still runs, and the summary names
  task A and the hygiene failure. (satisfies: R-5, R-9)
- [ ] A task stamped `feat/old` whose PRD now resolves to `feat/new` is skipped,
  its state stays `ready`, the other tasks complete, and the run exits 1.
  (satisfies: R-6, R-9)
- [ ] A task in `feat/b` that is blocked by a task in `feat/a` is not spawned,
  and the summary names both branches. (satisfies: R-7, R-9)
- [ ] The run banner lists `feat/a (prd)` and `feat/x (document)`.
  (satisfies: R-10)
- [ ] `aet epic set feat/a` fails as an unknown command. A queue envelope with
  an `epic` key prints one warning, and the key is absent after the next
  envelope write. (satisfies: R-11)
- [ ] `aet epic list` prints `feat/a` and `feat/b` with their task counts.
  (satisfies: R-12)
- [ ] `aet ship open-epic` with no argument refuses when two branches are
  queued and names them. `aet ship open-epic feat/a` opens a PR titled from
  `a-prd.md`. (satisfies: R-13, R-14)
- [ ] `aet docs lint` passes, and `grep -r "aet epic set" skills docs` finds
  only ADR-076 and ADR-083. (satisfies: R-15)
- [ ] The existing `pr-per-task` orchestrator tests pass unchanged.
  (satisfies: R-16)

## Technical Notes

- The resolution change is local to `resolve_integration_branch_for_task` and
  `derive_integration_branch_from_prd` (`src/aet/branch_ref.py`). Removing the
  envelope step also removes the `read_epic` call from resolution.
- `run_batch` already calls `resolve_integration_branch_for_task` per task
  when it records task metadata. The same result must also feed
  `create_worktree`, the hygiene check and the mismatch guard.
- `enforce_base_hygiene` (`src/aet/cli/orchestrator.py`) takes one branch now.
  The run keeps a per-branch result cache.
- The mismatch guard (`check_task_epic_mismatch`, `src/aet/branch_ref.py`) keeps
  its comparison. Only the response in `run_batch` changes: add the task to a
  run-local exclude set instead of setting `stop_spawn`.
- Skipped tasks must not count toward the systemic failure breaker, because
  their state does not change.
- `_get_staged_branches` and `_branches_to_flush_for_blocked_tasks` already
  iterate per branch. They need tests with two branches, not code changes.
- `read_epic`, `set_epic` and `clear_epic` leave the backend interface
  (`src/aet/backends/base.py`, `src/aet/backends/git_refs_backend.py`).
  `src/aet/cli/setup.py` also reads the epic and needs the same change.
- The change touches three subsystems: `src/aet/` resolution and run,
  `src/aet/` ship and epic commands, and `skills/`. The story breakdown must
  split along these lines.

## Risks

- **Cross-epic file conflicts.** Two epics that edit the same files each
  integrate cleanly into their own branch. The conflict shows only when the
  second epic PR targets trunk. Mitigation: `aet epic list` shows which epics
  are in flight; conflict resolution stays a human step at epic PR time.
- **Derived names change.** Projects that rely on the bare PRD stem as the
  branch get a `feat/` name. Stamped tasks keep their stamp, and R-6 skips
  them with a remedy instead of moving them. Unstamped tasks move to the new
  name. Mitigation: the R-11 warning names the old envelope branch, and the
  remedy is a `branch:` line in the PRD.
- **Slot use.** One large epic can hold all `--max-jobs` slots. Accepted for
  this PRD.

## Resolved Questions

- The `feat/` prefix is fixed. A PRD that needs another branch name declares
  `branch:`. No config key is added.
- A cross-epic dependency is checked at spawn only (R-7). `aet sprint add` does
  not warn, because a PRD `branch:` edit after intake can create the
  dependency later.

## Delivery

| Plan | Requirements | Blocked by |
| --- | --- | --- |
| `pep-01-prd-names-the-epic` | R-1, R-2, R-11, R-12, R-15 | — |
| `pep-02-run-drives-many-epics` | R-3, R-4, R-5, R-8, R-10, R-16 | `pep-01` |
| `pep-03-faults-stop-their-own-scope` | R-6, R-7, R-9 | `pep-02` |
| `pep-04-open-epic-by-branch` | R-13, R-14, R-15 | `pep-01` |

*Stage: scope-validated*
*Next step: `aet sprint add <plan>` then `/aet-drive` (or `aet run-one <id>`)*

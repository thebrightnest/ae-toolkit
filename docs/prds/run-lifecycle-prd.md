---
id: run-lifecycle
status: accepted
---

# PRD: Run Lifecycle — Stop, Teardown, Shared Lease, Handoff Growth

## Overview

Four defects make an `aet run` hard to stop, hard to retry and unsafe to run
next to another run. An operator stop is recorded as a countable timeout. A
standalone `aet run-one` leaves its task `in_progress`. A requeued task
reuses its dirty worktree, so teardown fails on every attempt. The run lease
lives in each checkout, while the git-refs queue is shared by every linked
worktree. The handoff note repeats entries and drops the newest one. This PRD
adds `aet run stop`, records an operator stop as `canceled`, snapshots dirty
worktrees before teardown, moves the lease to the common git directory, and
scopes the handoff note to one task. ADR-085 records the decisions.

## Intake Triage

Enhancement that closes four defects shown in v1.23.0 code. The fixes change
failure classification (ADR-060), lease scope (ADR-082) and worktree policy,
which needs a PRD and an ADR rather than a targeted bug fix. Work class:
`critical`, because the change decides task state after a stop, what work
survives a teardown, and which runs may write the queue.

## Evidence

From `content/backlog/client-run-mining-report-2026-10-28.md`, problems 6, 7,
9 and 11, and `content/backlog/no-command-stops-a-live-run.md`, checked
against v1.23.0 (`3d626d11`):

- **Operator stop is a timeout.** After `Received signal 15`, the log says
  `<id> killed by timeout; leaving failed` (6 runs in Client B, also seen in
  ae-toolkit). The `finally` in `run_batch` (`src/aet/cli/orchestrator.py`)
  calls `_cleanup_task(task_id, -1)`. `_finalize_task` sets `is_timeout` for
  any `ret < 0`, appends a countable `timeout` signature, and `_cleanup_task`
  adds the failure to the systemic tally. The child's own
  `failure.classify(shutdown=True)` returns `canceled`, which the breaker
  never records. ADR-060 decision 1 classes every signal death as timeout.
- **`run-one` leaves `in_progress`.** On failure or shutdown, the standalone
  `run-one` path calls no `_mark_failed` and no `teardown_worktree`; its
  `finally` only releases the lease. Client A needed `aet state reset` 4
  times. The batch leftover report labels the task `orphaned in progress`.
- **No stop command.** `run` is a plain Typer command (`src/aet/cli/main.py`)
  with no positional argument. Stopping a run needs `kill -TERM <pid>` with
  the PID from `aet status`. Client C had 21 signal stops.
- **Dirty worktree teardown.** `teardown_worktree` (`src/aet/worktree.py`)
  refuses a worktree with uncommitted files. `create_worktree` reuses the
  existing directory, dirty or not. `Worktree teardown failed for <id>` was
  logged 46 times in 15 Client C runs and 11 times in one Client B run, once
  per requeue.
- **Lease per checkout.** `lease_path` (`src/aet/queue.py`) resolves to
  `<checkout>/.agents/work-queue.lease`. Queue state lives in
  `refs/aet/tasks/*` and `refs/aet/meta/queue`, which every linked worktree
  shares. Client B started a second `aet run` three times while another run
  was live; it did nothing, exited 0 and reported `Leftover: 1 orphaned in
  progress`.
- **Flush refused under lease.** `train.flush` runs `aet_state.py transition
  <id> awaiting_merge merged` and ignores the return code. `cmd_transition`
  calls `lease_guard`, which refuses while another run holds the lease. Seen
  twice on 2026-10-27 (`content/backlog/flush-merged-transition-silently-refused-under-lease.md`):
  `main` was pushed, the task stayed `awaiting_merge`.
- **Handoff growth.** `append_entry` (`src/aet/handoff.py`) always appends;
  entries carry no task id, and every task of a batch shares one note.
  `render_prompt_block` keeps the first 4,000 characters, so the oldest
  entries survive and the newest is cut. Client B reached 57 entries for one
  looping task.

## Goals

- An operator stops a run with one command, and the stopped tasks return to
  `ready` with no breaker penalty.
- No task is left `in_progress` after its run ends.
- A failed or requeued task never blocks its own next attempt with a dirty
  worktree, and its uncommitted work stays recoverable.
- Two runs never write one queue from two linked worktrees.
- A retry prompt shows the task's own newest handoff entries once each.

## Non-Goals

- Timeouts on validation, rebase and flush outside the agent session (CR-10).
- Retry from the failed stage instead of implement
  (`retried-task-restarts-at-implement.md`).
- A lease shared across separate clones or hosts.
- Escalation from SIGTERM to SIGKILL in `aet run stop`.
- Per-task progress in `aet status` (`run-progress-not-visible-per-task.md`).
- The `reason` field for refusals in `last-run.json` (CR-13).
- Garbage collection of snapshot refs for tasks that never close.

## Requirements

### Operator stop

- **R-1**: `aet run stop [RUN_ID]` sends SIGTERM to the orchestrator PID
  recorded for the run, waits until the run writes its return code, and
  prints the settlement summary. With no `RUN_ID`, it stops the only live run
  of the checkout; with zero or several live runs, it exits non-zero and
  lists them.
- **R-2**: `aet run stop` exits non-zero with a message when the run does not
  exist or is not alive. When the run does not settle within `--timeout`
  seconds (default 120), it exits non-zero and reports that the run is still
  live.
- **R-3**: `aet run` keeps every current option and behavior;
  `aet run --follow` and the other options parse as before.
- **R-4**: When a batch run shuts down on a signal, each task whose session
  it ends is recorded as `canceled`: no countable failure signature, no
  systemic tally increment, no triage session, and the task returns to
  `ready`. The log prints `<id> canceled by operator stop; returned to ready`.
- **R-5**: A session killed by the wall-clock backstop or the stall watchdog
  is still recorded as `timeout`, as ADR-060 states.
- **R-6**: A standalone `aet run-one` whose session fails marks the task
  `failed` with a failure signature. A standalone `aet run-one` that shuts
  down on a signal records `canceled` and returns the task to `ready`. In
  neither case does the task stay `in_progress`.
- **R-7**: The stage record of a canceled session carries the `canceled`
  failure class, not `timeout`. The run summary of a stopped run holds
  `canceled: true`. The count of a canceled task in the run summary belongs to
  `tlc-02-run-summary-counts-end-states`: requeued, never in
  `attempts_failed`.

### Worktree teardown

- **R-8**: Before a task worktree is removed after a failure, a cancel or a
  requeue, its tracked changes and non-ignored untracked files are saved as
  one commit under `refs/aet/wip/<task-id>/<attempt>`, whose parent is the
  task branch tip. The worktree is then removed, and the log names the ref.
- **R-9**: The snapshot does not move the task branch or its tip.
- **R-10**: `create_worktree` never hands a dirty existing worktree to a
  session. It snapshots it as in R-8, removes it, and creates the worktree
  again from the task branch tip.
- **R-11**: The handoff note for the next attempt names the snapshot ref.
- **R-12**: `refs/aet/wip/*` is never pushed by the git-refs backend.
  Terminal closure of a task (`merged` or `abandoned`) deletes its snapshot
  refs.

### Shared run lease

- **R-13**: The run lease lives at `<git-common-dir>/aet/work-queue.lease`. A
  second `aet run` or `aet run-one` from any linked worktree of the
  repository is refused with exit code 75 and a message that names the
  holding run id.
- **R-14**: Lease checks also honor a live lease at the per-checkout legacy
  path, so a run started before the upgrade keeps its lease until it ends.
- **R-15**: The flush's own `awaiting_merge → merged` transition passes the
  run lease while the flush holds `integration_lock`. Every other queue
  mutation still needs the lease (ADR-082 decision 7).
- **R-16**: `train.flush` checks the return code of each seal transition. A
  refused seal appears in the `FlushResult` and in the command output with
  the task id and the reason.

### Handoff note

- **R-17**: Every handoff entry carries the `task_id` of the task that wrote
  it. `aet handoff append` takes it from `--task` or `AET_TASK_ID`.
- **R-18**: The prompt block of a task renders only that task's entries.
  Entries without a `task_id` render for every task.
- **R-19**: Identical entries render once, with the number of repeats.
- **R-20**: When the rendered block exceeds the cap, the oldest entries are
  dropped first; the newest entry always renders.
- **R-21**: The note's `schema_version` is 2, and the reader accepts version
  1 notes.

### Documentation and regression

- **R-22**: ADR-085 records the decisions; ADR-060 and ADR-082 name it as an
  amendment. `CONTEXT.md` defines operator stop and the snapshot ref.
  `skills/aet-drive/SKILL.md` names `aet run stop`. `docs/CLI.md` is
  regenerated.
- **R-23**: Existing tests pass unchanged, except where they assert the old
  stop, teardown, lease or handoff behavior.

## User Stories

- As an operator, I want to stop a live run with one command and find the
  stopped tasks ready again, so that a stop costs no manual reset and no
  breaker strike. (satisfies: R-1 to R-5, R-7)
- As an operator using `aet run-one`, I want the task to end `failed` or
  `ready`, so that I never reset it by hand. (satisfies: R-6)
- As an operator, I want a requeued task to start from a clean worktree while
  its unfinished files stay recoverable, so that teardown stops failing and
  no work is lost. (satisfies: R-8 to R-12)
- As an operator with several worktrees, I want a second run refused, so that
  two runs never write one queue. (satisfies: R-13, R-14)
- As an operator who ships during a live run, I want the merged task sealed,
  or the refusal shown, so that no task stays `awaiting_merge` in silence.
  (satisfies: R-15, R-16)
- As an implement agent on a retry, I want only my task's newest notes, once
  each, so that the prompt carries the latest evidence. (satisfies: R-17 to
  R-21)

## Acceptance Criteria

- [ ] `aet run stop` on a live detached run ends it, prints the settlement
  summary, and every stopped task is `ready` with no new failure signature.
  (satisfies: R-1, R-4)
- [ ] `aet run stop` on an unknown or ended run exits non-zero with a
  message. (satisfies: R-2)
- [ ] `aet run --follow` starts a run as before. (satisfies: R-3)
- [ ] After SIGTERM to a batch run, the log shows `canceled by operator
  stop`, the breaker store has no new entry, the stage record says
  `canceled`, and the run summary holds `canceled: true`. (satisfies: R-4,
  R-7)
- [ ] A session killed by the wall-clock backstop still logs
  `killed by timeout`. (satisfies: R-5)
- [ ] After a failed `aet run-one`, the task is `failed`; after SIGTERM to
  `aet run-one`, it is `ready`. (satisfies: R-6)
- [ ] A requeued task with uncommitted files leaves no
  `Worktree teardown failed` line; `refs/aet/wip/<id>/<attempt>` holds the
  files, and the branch tip is unchanged. (satisfies: R-8, R-9)
- [ ] A dirty leftover worktree is replaced by a clean one at the next spawn.
  (satisfies: R-10)
- [ ] The retry prompt names the snapshot ref. (satisfies: R-11)
- [ ] `aet state push` sends no `refs/aet/wip/*` ref; after `merged`, the
  task has no snapshot refs. (satisfies: R-12)
- [ ] With a run live in one linked worktree, `aet run` in a second linked
  worktree exits 75 and names the run. (satisfies: R-13)
- [ ] A lease at the legacy path still blocks a second run. (satisfies: R-14)
- [ ] `aet ship merge` during another live run leaves the task `merged`.
  (satisfies: R-15)
- [ ] A refused seal transition prints the task id and the reason.
  (satisfies: R-16)
- [ ] A task's retry prompt with 57 identical entries renders one entry with
  its repeat count, plus the newest entry, and no entry of another task.
  (satisfies: R-17 to R-20)
- [ ] A version 1 note renders without error. (satisfies: R-21)
- [ ] `aet docs lint` passes and `make validate` passes. (satisfies: R-22,
  R-23)

## Technical Notes

- `_handle_signal` (`src/aet/cli/orchestrator.py`) only sets
  `_shutdown_requested`. The `finally` of `run_batch` passes `-1`; the
  wall-clock path passes `-9`. The two differ only by value. A canceled
  marker passed from the `finally` to `_finalize_task`, checked before
  `is_timeout`, separates them.
- `_TRIAGE_DEFAULT_ACTIONS` maps `canceled` to `quarantine`. R-4 bypasses
  triage for a canceled task.
- `gfe-02-bounded-retries` excludes `canceled` from the attempt cap. Both
  PRDs edit `_finalize_task` and `run_batch`, so the stop plan follows
  `gfe-02`.
- `tlc-02-run-summary-counts-end-states` (`telemetry-correctness-prd.md`)
  adds the `end_state` map, `tasks_requeued`, `attempts_failed` and `reason`
  to the run summary, and counts a canceled task as requeued, outside
  `attempts_failed`. `tlc-01` and `tlc-02` follow `rl-01`; the `reason` field
  (CR-13) belongs to the telemetry PRD.
- `aet run` becomes a Typer group with `invoke_without_command=True`; the
  callback keeps today's options. `_spawn_detached` writes
  `.agents/runs/<run-id>/pid`; `liveness.is_run_alive` decides liveness.
- `_requeue_task` touches neither the worktree nor the branch. Committed work
  stays on the local task branch, which only `aet ship` pushes.
  `_note_branch_state` already writes branch commits into the handoff note.
- The snapshot commit can be built with a temporary index
  (`GIT_INDEX_FILE`, `git add -A`, `write-tree`, `commit-tree`,
  `update-ref`), so neither the worktree index nor the branch changes.
- `git rev-parse --git-common-dir` is already used by `src/aet/project_id.py`
  (ADR-022).
- The git-refs backend pushes with forced refspecs. R-12 needs the refspec
  list checked, not only the new ref name.
- Batch children inherit `AET_RUN_ID`, so every task of a batch writes one
  handoff note. The orchestrator sets the task id in the child environment;
  R-17 reads it from there.

## Risks

- **Group conversion.** A Typer group can shadow a future positional
  argument of `aet run` and changes its help output. Tests in
  `tests/cli/test_run_dispatcher.py` and `tests/test_aet_run_dispatch.py`
  guard the current options.
- **Canceled work hides a real fault.** A task that hangs until the operator
  stops it returns to `ready` with no strike. Accepted: the wall-clock
  backstop and stall watchdog still record `timeout`.
- **Snapshot refs grow.** Each failed attempt adds one local ref until the
  task closes. Accepted: refs are small, and closure deletes them.
- **Lease move during a live run.** R-14 covers a run started before the
  upgrade. A run on the old code does not see a new-path lease; the upgrade
  happens between runs.
- **Flush exemption.** A ship flush seals the tasks of its own flush batch
  during another run. It holds `integration_lock`, and the run's own flush takes the
  same lock, so the two never interleave.

## Open Questions

- None.

## Delivery

| Plan | Requirements | Blocked by |
| --- | --- | --- |
| `rl-01-operator-stop-is-canceled` | R-4 to R-7, R-22 (ADR-060, CONTEXT.md), R-23 | `gfe-02-bounded-retries` |
| `rl-02-aet-run-stop` | R-1 to R-3, R-22 (skill, CLI.md), R-23 | `rl-01` |
| `rl-03-dirty-worktree-snapshot` | R-8 to R-12, R-22 (CONTEXT.md), R-23 | `rl-01` |
| `rl-04-shared-run-lease` | R-13 to R-16, R-22 (ADR-082), R-23 | — |
| `rl-05-handoff-per-task` | R-17 to R-21, R-23 | — |

## Scope Validation

Checked on 2026-10-28 against `CONTEXT.md`, ADR-022, ADR-030, ADR-039,
ADR-060, ADR-069, ADR-071, ADR-082 and ADR-084, and against the v1.23.0 code:

- ADR-060 decision 1 classes every signal death as `timeout`; ADR-071
  decision 4 states that an operator stop is not evidence about the work.
  ADR-085 decision 1 resolves the conflict for orchestrator shutdown and
  amends ADR-060. `rl-01` records the amendment.
- `CONTEXT.md` **Stall Timeout** applies `timeout` to any signal death.
  `rl-01` narrows it.
- `CONTEXT.md` **Run Liveness** names the **Run Lease**, which has no
  definition. `rl-04` adds it.
- ADR-082 decision 7 limits lease exemptions to add-only writes. ADR-085
  decision 5 adds the flush seal; `rl-04` records the amendment.
- ADR-084 decision 2 excludes `canceled` from the attempt cap. `rl-01`
  depends on `gfe-02-bounded-retries` for that reason.
- `telemetry-correctness-prd.md` (draft, ADR-086) builds its run-summary
  counts on `rl-01`: `tlc-02` counts a canceled task as requeued and leaves it
  out of `attempts_failed`. `tlc-01` and `tlc-02` follow `rl-01`, and
  `tlc-03` follows `rl-04`. The `reason` field (CR-13) stays in that PRD.
- "Snapshot" names only the `refs/aet/wip/*` ref; the flush batch is not
  called a snapshot in this PRD.
- All five plans use `pipeline: standard`. The UI coverage lens does not
  apply: the change is CLI-only.

## Divergence Summary

*Recorded: 2026-10-28 — Branch: rl-04-shared-run-lease*

### Changed from plan — rl-04

- None.

### Added (unplanned) — rl-04

- `rl-04`: fallback definition `UTC = timezone.utc` in `src/aet/perf_report.py` for Python runtime compatibility.

### Deferred — rl-04

- None.

*Stage: synced*
*Next step: run `aet-ship`*

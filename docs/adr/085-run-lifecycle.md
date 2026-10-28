---
subject: run-lifecycle
relates: [22, 30, 39, 60, 69, 71, 82]
---

# An Operator Stop Is Canceled, and One Lease Guards the Shared Queue

## Status

Proposed. Amends ADR-060 decision 1 and ADR-082 decision 7. PRD:
`docs/prds/run-lifecycle-prd.md`.

## Context

ADR-060 classes every signal-killed session as `timeout`, so that the
wall-clock backstop and the stall watchdog give one outcome. The batch parent
applies the rule to its own shutdown too: the `finally` of `run_batch` ends
each live child and finalizes it with exit `-1`, which `_finalize_task` reads
as a timeout. An operator stop therefore writes a countable `timeout`
signature, raises the systemic tally and leaves the task `failed`. ADR-071
decision 4 states the opposite intent: an operator stopping a shift is not
evidence about the work. No command stops a run; operators send SIGTERM by
PID. A standalone `aet run-one` leaves its task `in_progress` after a failure
or a stop.

A requeued task reuses its worktree. `teardown_worktree` refuses a worktree
with uncommitted files, and `create_worktree` hands the same dirty directory
to the next session, so teardown fails on every attempt. Client telemetry
logged 57 such failures in two projects.

The run lease is a file in each checkout, while queue state lives in
`refs/aet/*`, which every linked worktree of the repository shares. A run in a
second linked worktree sees no lease and writes the same queue. A flush from
`aet ship merge` during another run is refused by the lease when it seals the
merged task, and the refusal is silent.

Handoff entries carry no task id. Every task of a batch writes one note per
run, entries are never deduplicated, and the prompt block keeps the oldest
4,000 characters, so the newest entry is cut first.

## Decision

1. **An operator stop is `canceled`.** When the orchestrator ends a session
   because it received a shutdown signal, the session is `canceled`, not
   `timeout`. It writes no failure signature, raises no breaker count, runs
   no triage, and the task returns to `ready`. The run summary counts it as
   requeued, not as a failed attempt. ADR-060 decision 1 still holds
   for every other signal death: the wall-clock backstop and the stall
   watchdog record `timeout`. `aet run stop [RUN_ID]` sends that signal; `run`
   becomes a command group, following the ADR-039 noun-verb taxonomy.
2. **No run leaves its task `in_progress`.** A standalone `aet run-one` marks
   a failed task `failed` with a signature, and returns a stopped task to
   `ready`.
3. **Uncommitted work is saved to a snapshot ref before teardown.** Before a
   task worktree is removed after a failure, a cancel or a requeue, its
   uncommitted files are committed under `refs/aet/wip/<task-id>/<attempt>`,
   with the task branch tip as parent. The branch does not move. A dirty
   worktree is never reused; it is snapshotted and created again from the
   branch tip. Snapshot refs are local and are deleted at terminal closure.
4. **The run lease lives in the common git directory.** The lease file is
   `<git-common-dir>/aet/work-queue.lease`, so every linked worktree of the
   repository sees one lease. A live lease at the legacy per-checkout path is
   still honored. Separate clones keep separate leases.
5. **A flush seals its own merges under the integration lock.** The
   `awaiting_merge → merged` transition that a flush makes passes the run
   lease while the flush holds `integration_lock`. Every other queue mutation
   still needs the lease. The flush checks each seal and reports a refusal.
6. **A handoff entry belongs to one task.** Each entry carries its `task_id`.
   A task's prompt block renders its own entries and run-level entries,
   renders identical entries once with a count, and drops the oldest entries
   first when it exceeds the cap.

## Consequences

- An operator can stop a run at no cost to the stopped tasks; a stopped task
  needs no reset.
- A task that hangs until the operator stops it is not counted. The
  wall-clock backstop and the stall watchdog still count real hangs.
- Teardown no longer fails on dirty worktrees, and the work of a failed
  session stays recoverable from its snapshot ref.
- Two linked worktrees cannot run on one queue at the same time. Two separate
  clones still can; their refs meet only through push and fetch.
- `aet ship merge` during a live run seals the task, and `aet state heal` is
  no longer needed after it.
- A retry prompt carries the newest evidence of its own task.

## Alternatives Considered

- **Keep ADR-060 and leave a stopped task `failed` but uncounted.** Rejected:
  the operator must requeue every stopped task by hand.
- **Top-level `aet stop`.** Rejected: it breaks the ADR-039 taxonomy.
- **Commit uncommitted work onto the task branch.** Rejected: the retry builds
  on half-done, possibly broken work.
- **`git stash`.** Rejected: the stash is shared by all worktrees and keyed by
  position, not by task.
- **A lease in a pushed ref with a heartbeat.** Rejected for now: liveness
  across hosts is new design, and no observed failure involved two clones.
- **Check the seal return code only, with no exemption.** Rejected: every ship
  during a run would need `aet state heal`.
- **One handoff note per task.** Rejected: ADR-069 and `aet handoff show`
  treat the note as run-scoped; a task filter solves the growth.

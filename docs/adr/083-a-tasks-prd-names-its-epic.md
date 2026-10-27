---
subject: parallel-epics
relates: [39, 44, 45, 76, 79]
---

# A Task's PRD Names Its Epic, and Epics Run in Parallel

## Status

Proposed. Amends ADR-076 decisions 1, 2 and 4. Applies ADR-045 §2 to every
task in a batch. PRD: `docs/prds/parallel-epics-prd.md`.

## Context

ADR-076 declares one active epic in the queue envelope and resolves a task's
integration branch through it before the PRD filename. That model fits a queue
that holds one epic. A queue that holds tasks from several PRDs breaks it:

- Every task without a PRD-declared `branch` resolves to the one active epic.
  Unrelated PRDs integrate into one branch and ship in one PR.
- `run_batch` (`src/aet/cli/orchestrator.py`) bases every worktree on one
  branch resolved per run, although ADR-045 §2 bases a task on the live tip of
  its own integration branch.
- A stamp mismatch on one task halts the whole batch.

On 2026-10-27 the `dhl-agentic-rac` queue held ready tasks from 5 PRDs with
one active epic. The operator could run only one task at a time.

The rest of the `single-pr` machinery already works per branch. The merge
train flushes per branch (ADR-079), task stamps record a branch per task, and
the integration lock serializes integration across all tasks (ADR-045 §5).

## Decision

1. **A task's PRD names its epic.** In `single-pr` mode the integration branch
   resolves in this order: CLI `--base`, `AET_WORK_BASE_BRANCH`, task stamp,
   PRD frontmatter `branch`, the branch derived from the PRD filename, config
   `integration_branch`, trunk. A declared `branch` stays the primary form, as
   ADR-076 decision 1 requires. The derived name is the fallback when the PRD
   declares none.
2. **The derived name is `feat/<stem>`.** The stem is the PRD filename stem
   with a trailing `-prd` removed.
3. **The envelope active epic is retired.** It is no longer a resolution step.
   `aet epic set` and `aet epic clear` are removed with no alias (ADR-039).
   `aet epic list` replaces `aet epic show` and lists every integration branch
   that queued tasks resolve to. This replaces ADR-076 decision 2, "one active
   epic at a time", and step 5 of the ADR-076 decision 4 order.
4. **A run drives many epics.** Each task's worktree is based on the live tip of
   its own integration branch. A missing epic branch is created locally from the
   trunk tip and is not pushed. Base hygiene is checked once per branch.
   Implementation runs concurrently up to `--max-jobs` across all branches.
   Integration stays serialized under the one integration lock.
5. **A fault stops only its own scope.** A stamp mismatch skips that task. A
   hygiene failure skips that branch's tasks. A task whose blocker is on a
   different integration branch is not spawned. Other work continues, and the
   run exits non-zero with each skip and its remedy in the summary. The
   mismatch check stays fail-closed for the task it finds.
6. **An epic PR is opened by branch.** `aet ship open-epic` takes the branch.
   It reads the PR title and body file from the frontmatter of the PRDs that
   resolve to that branch.

## Consequences

- Several epics in one queue run in parallel with no operator step per epic.
- An operator does not declare an epic before a run. The PRD carries the
  declaration, or its filename does.
- Two PRDs that declare one `branch` form one epic. ADR-076's multi-PRD epic
  still works, through the PRD instead of the envelope.
- Cross-epic file conflicts appear at epic PR time, not during the run.
- Projects that use the bare PRD stem as the branch name see a `feat/` name.
  Stamped tasks keep their stamp and are skipped with a remedy if they diverge.
- Queue envelopes that carry an `epic` key lose it on the next write, after one
  warning that names the branch.
- `pr-per-task` mode does not change.

## Alternatives Considered

- **Keep the envelope epic as a fallback.** Rejected: a task whose PRD declares
  no branch would still re-target silently to the active epic.
- **Require a declared `branch` in every PRD.** Rejected: every PRD would need
  one more line with no information, and intake would refuse existing plans.
- **A lock per integration branch.** Deferred: the single lock is correct, and
  integration is short compared with implementation.

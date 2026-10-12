---
subject: merge-train
relates: [11, 29, 45, 64, 78]
---

# Merge Train: Stage Under the Lock, Validate Once per Batch

## Status

Proposed (2026-10-12). Delivered by `mtv-04-merge-train-staging-and-flush`
and `mtv-05-train-bisect-and-eject` (PRD:
`docs/prds/merge-train-validation-prd.md`).

## Context

Every completed task is integrated under `integration_lock` by rebasing onto
the integration tip and running the full validation command. Under parallel
`aet run` the lock serializes those suite runs: N finished tasks wait behind N
sequential suites, though each task already passed QA on its own tree. The
only new fact a post-rebase run establishes is that the task combined with
what landed since still passes — and that fact can be established once for
many tasks.

## Decision

1. **Staging, not merging, under the lock.** `integrate()` rebases onto the
   train tip, applies guards, and squash-merges onto the local ref
   `refs/aet/train/<integration-branch>` with compare-and-swap. No suite runs
   while the lock is held. The ref is never pushed and is rebuildable from task
   records.
2. **No new state.** A staged task stays `awaiting_merge` with a train marker.
   ADR-011's forward-only lifecycle is unchanged.
3. **Flush.** The suite runs once on a snapshot of the staging tip, outside the
   lock. Green: the integration branch fast-forwards to the snapshot and is
   pushed, the snapshot's tasks become `merged` with their staged commits as
   merge evidence (ADR-064), and a `batch` verdict stamped with the tree hash is
   recorded.
4. **Flush triggers:** the run has no in-progress or ready work; a task is ready
   except for staged blockers; `aet ship open-epic`; `aet ship merge`.
   Dependents therefore only start from a validated tip.
5. **Invariant.** The integration branch — trunk in `pr-per-task` — moves only
   to a tree with a passing batch verdict.
6. **Red flush.** A deterministic prefix bisect finds the first failing task;
   it is ejected (marker cleared, stays `awaiting_merge` with diagnostics) and
   the rest re-stack and flush again. Because of decision 4, no batch-mate
   depends on another, so ejection never cascades. Any non-suite failure halts
   integration fail-closed (ADR-029).

## Consequences

- One suite per batch on green; ⌈log₂ n⌉ extra runs only on red.
- Failures surface at flush, not at each integration.
- `merged` gains a precondition: a green flush covering the task.

## Alternatives Considered

- **Merge directly, validate afterwards** — rejected: a red tip could reach trunk.
- **Optimistic full run per task outside the lock** — rejected: still one suite
  per task, plus retries under contention.
- **A new `staged` state** — rejected: the marker suffices and avoids touching
  every state reader.
- **Fixed batch size** — rejected: decision 4 bounds batches where it matters.

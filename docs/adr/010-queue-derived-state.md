---
subject: work-state
---

# Queue State Is Derived from Persistent Facts

## Status

Superseded by [ADR-011](011-forward-only-deterministic-work-state.md).

## Context

`aet-work` stores queue state in `.agents/work-queue.json`. Over time, the file accumulated responsibilities it could not fulfill reliably:

- `init-queue`, `sync`, and `status` all derived status from ground truth and mutated or compared the stored `status` field.
- `sync` promoted blocker-satisfied tasks to `unblocked`, but `aet-state derive` ignored blockers and called the same tasks `planned`.
- Every `unblocked` task produced a stored-vs-derived mismatch warning, which trained users to ignore warnings.
- Orphan detection overwrote workflow status with `orphaned`, conflating drift detection with state.
- `sync` grew into a second full rebuild of the queue instead of an incremental append helper.

The 2026-06-17 work-queue review retro traced these symptoms to a single root cause: the queue tried to store actionable state that should be computed on read.

## Decision

Separate **persistent facts** from **derived actionable state** in the work queue:

1. **Stored facts only.** `.agents/work-queue.json` stores `plan_file`, `blocked_by`, `blocks`, `branch`, `worktree`, `merge_commit`, and terminal human decisions (`abandoned`/`failed`). It does not store `blocked` or `unblocked`.
2. **Single derivation helper.** `aet-state derive` is the only place that computes actionable state from facts + git/filesystem. It returns:
   - `merged` — branch or merge commit is on `origin/main`.
   - `in-progress` — local branch exists.
   - `unblocked` — plan exists, no branch, all blockers are `merged`/`abandoned`.
   - `blocked` — plan exists, no branch, some blocker is not terminal.
3. **Thin helpers.** `init-queue` rebuilds facts from `docs/plans/*.md`; `sync` only appends new plans and recomputes `blocks`; `status` / `next` / the orchestrator use derived state.
4. **Drift is reported, not stored.** A missing plan file is reported as plan drift; the queue entry is not overwritten with an `orphaned` status.
5. **No PRD intake.** `init-queue` and `sync` continue to read only `docs/plans/*.md`. PRDs are pre-planning artifacts and must not appear in the queue.

## Consequences

- **Easier:** `sync` is fast and safe to run after adding new plans.
- **Easier:** No false mismatch warnings for ordinary pickable tasks.
- **Easier:** Manual edits to `blocked_by` do not require a re-derive step to become actionable.
- **Harder:** `status`, `next`, and the orchestrator must always derive before acting; they cannot rely on a pre-computed `unblocked` label.
- **Harder:** Existing consumer repos with stored `unblocked`/`blocked` statuses will be normalized to `planned` on the first `init-queue` rebuild.

## Alternatives Considered

1. **Keep stored `unblocked` and make `derive` respect it.** Rejected: it preserves two sources of truth and leaves the mismatch-warning problem unsolved.
2. **Derive only for `status` but keep stored labels for `next` and the orchestrator.** Rejected: the same inconsistency would reappear whenever someone edits the queue file.
3. **Move the entire queue to GitHub issues.** Rejected in ADR 006 and the systemic improvement analysis: violates the toolkit’s agent- and infra-agnosticism, and GitHub has poor native DAG support.

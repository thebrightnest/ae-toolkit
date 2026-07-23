# Bug Report: `aet-ship` closure requires too many manual steps and falls through to `aet-state record-merge`

## Metadata

- **Reported:** 2026-07-23
- **Severity:** medium
- **Status:** open

## Symptoms

Shipping a plan through `aet-ship` and then closing it after merge currently
requires the operator to remember and run multiple commands with overlapping
responsibilities:

1. `aet ship open docs/plans/<plan>.md` — opens the PR.
2. Merge the PR (manually, via GitHub UI, or via `gh pr merge`).
3. `aet ship close <task_id> docs/plans/<plan>.md` — attempts to record closure.
4. If the task is not in `.agents/work-queue.json` or is not in
   `awaiting_merge`, step 3 fails with `Task not found`.
5. Work around with `aet state record-merge <task_id> --merge-commit <sha>`,
   which requires the operator to look up the merge commit SHA.

Even when step 3 succeeds, the user must supply both `<task_id>` and the plan
path, even though the task id is already in the plan frontmatter and the merge
commit is already on `origin/main`.

Observed today while closing `epi-04-orchestrator-run-preconditions`: after the
PR merged and the plan markdown was updated to `status: merged`, `aet status`
still showed the task as `awaiting_merge` because the queue entry had not been
recorded. The final close required `aet state record-merge` with an explicit
SHA instead of a single `aet-ship` command.

## Reproduction Steps

1. Complete a plan and run:

   ```bash
   aet ship open docs/plans/epi-04-orchestrator-run-preconditions.md
   ```

2. Merge the resulting PR.
3. Run:

   ```bash
   aet ship close epi-04-orchestrator-run-preconditions docs/plans/epi-04-orchestrator-run-preconditions.md
   ```

   This only works if the orchestrator has already moved the task to
   `awaiting_merge` in the queue. If the task was not queued, or the queue was
   reset, it fails with:

   ```
   Task not found: epi-04-orchestrator-run-preconditions
   ```

4. Recover by running:

   ```bash
   aet state record-merge epi-04-orchestrator-run-preconditions \
     --merge-commit ed12bf9bb28df1756fbbcd66d09fbbdb84c1bee3
   ```

   The SHA must be discovered manually from `git log origin/main` or the PR
   page.

## Root Cause

- `aet ship close` only knows how to look up a task by id in the ephemeral
  work queue. It does not fall back to reading the plan file or verifying the
  branch state on `origin/main`.
- `aet ship close` does not resolve the merge commit itself; it relies on the
  queue already having it or on the caller providing it via
  `--merge-commit`.
- The queue is considered the sole source of truth for runtime state, but the
  plan markdown frontmatter is what humans and `aet status` consult. Keeping
  them in sync is manual.
- ADR-013 already decided that "Closure has one owner: `aet-ship`. There is no
  separate `record-merge` step for the user to remember." The current
  implementation has not yet converged on that decision.

## Impact

- Every shipped plan incurs extra manual steps and a chance of desynchronizing
  the queue from the repo state (plan file says `merged`, queue still says
  `awaiting_merge`).
- `aet status` becomes misleading until the manual `record-merge` step is run.
- The fallback command (`aet state record-merge`) lives in a different
  subcommand namespace, increasing cognitive load and the risk of operator
  error.

## Proposed Fix

Make `aet ship close` the single owner of closure:

1. Accept either a plan file path or a task id:

   ```bash
   aet ship close docs/plans/<plan>.md
   aet ship close <task-id>
   ```

2. When given a plan path, derive the task id from the plan frontmatter.
3. Verify the plan's branch on `origin/main` (or the configured trunk) and
   resolve the merge commit from the branch ancestry, removing the need for
   `--merge-commit` in the common case.
4. Record the merge in the queue/history and update the plan markdown
   frontmatter/footer to `merged` in one step, committing and pushing the
   status change (per ADR-034).
5. Keep `--merge-commit` as an override for ambiguous cases only.

## Related

- ADR-013: queue-as-ephemeral-sprint-board
- ADR-034: settled-from-versioned-plan-data
- `docs/plans/aet-ship-squash-merge-core-plan.md`
- `docs/plans/bs-01-aet-ship-merge-verification.md`
- `docs/plans/qes-05-ship-closure.md`

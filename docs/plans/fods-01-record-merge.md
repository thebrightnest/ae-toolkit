---
id: fods-01-record-merge
blocked_by: []
size: M
---

# Plan: Deterministic Merge Recording (`aet-state record-merge`)

## Context

- PRD: `docs/prds/forward-only-deterministic-work-state-prd.md` (Workstream A)
- ADR: `docs/adr/011-forward-only-deterministic-work-state.md`
- Prior work: `bs-01-aet-ship-merge-verification` and `aet-ship-squash-merge-core` added merge verification **as prose** in `aet-ship/SKILL.md` (Steps 12/12a/13) plus a note instructing the agent to hand-edit `merge_commit` into `.agents/work-queue.json`. The 2026-06-18 audit confirmed the consequence: `merge_commit` has **zero deterministic writers**, `post-ship-verify` has no implementation, and squash-merged tasks therefore re-derive to `unblocked`.

This plan converts that prose procedure into a deterministic executable so the merge record can neither be skipped nor mis-written. It is the first, standalone step of the PRD: it stops the active resurrection bug under the **current** queue model (the recorded `merge_commit` is verifiable by today's `derive`), requires **no schema change**, and becomes the foundation the state spine (Workstream B) builds on.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Tasks

1. **Add `record-merge` to `aet-work/bin/aet-state`** — M

   New subcommand `aet-state record-merge <task_id> [queue]`:

   - `git fetch origin`.
   - If the task's `branch` is an ancestor of `origin/main`, use its tip as the merge commit.
   - Else resolve via `gh pr view <branch> --json mergeCommit` and verify the SHA is an ancestor of `origin/main`.
   - Else apply the diff-equivalence fallback in `aet-ship/references/squash-merge-handling.md`; if still unresolved, **exit non-zero and mutate nothing**.
   - On success, write `merge_commit`, `status: merged`, and `merged_at` atomically through the existing `transition` path (reusing `validate_transition`).

2. **Wire `aet-ship` to invoke `record-merge`** — S

   Replace the prose in `aet-ship/SKILL.md` (Steps 12/13) that tells the agent to hand-edit `.agents/work-queue.json` with a single `aet-state record-merge <task_id>` call. The skill no longer describes editing queue JSON by hand.

3. **Stop the orchestrator marking unverified work terminal** — S

   On pipeline success the orchestrator records a non-terminal `awaiting_merge` status instead of `done`, so finished-but-unmerged work is never archived as complete or counted as a satisfied blocker. Full lifecycle semantics land in Workstream B; this task only removes the false-terminal write.

4. **Tests + package** — S

   Unit-test `record-merge` across the regular-merge, squash-merge (`gh`), diff-fallback, and unresolved (non-zero exit, no mutation) paths. Run `make validate` and `make package`.

## Dependencies

None. The authoritative dependency declaration is `blocked_by: []` in the frontmatter; this is the first task of the PRD.

## Validation Steps

- [ ] `aet-state record-merge` writes `merge_commit` + `status: merged` + `merged_at` atomically, or exits non-zero without mutating the queue.
- [ ] A squash-merged task (branch not an ancestor; real merge commit is) is recorded as `merged` and no longer derives to `unblocked`.
- [ ] `grep` of `aet-ship/SKILL.md` shows no instruction to hand-edit `merge_commit` in the work queue.
- [ ] The orchestrator no longer writes `done` on pipeline success; it writes `awaiting_merge`.
- [ ] Tests cover the regular / squash / fallback / unresolved paths.
- [ ] `make validate` passes and `make package` regenerates the `.skill` files.

## Rollback Plan

Revert the `aet-work/bin/aet-state`, `aet-ship/SKILL.md`, and `aet-work/bin/orchestrator` changes and re-run `make package`. No schema migration is performed, so the queue stays readable by the prior tooling.

---

_Stage: reviewed_

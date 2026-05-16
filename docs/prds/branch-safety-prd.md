# PRD: Toolkit-Level Branch Safety

## Overview

Add automatic merge verification to `aet-ship`, `aet-pipeline-implement`, and `aet-work` to prevent the "Local Merge Trap" — a silent data-loss scenario where branches are deleted after being "merged" locally but their commits never reach `origin/main`.

## Goals

- `aet-ship` halts with a clear warning if `git merge-base --is-ancestor HEAD origin/main` fails before any branch deletion
- `aet-pipeline-implement` supports a `merged` stage after `synced` and updates the work queue with `merge_verified`
- `aet-work` checks `merge_verified` on the previous task before starting the next task
- All three skills reference the same verification command: `git merge-base --is-ancestor <ref> origin/main`
- Backward-compatible: old work queues without `merge_verified` are treated as unverified, not broken

## Non-Goals

- Do not add git hooks (rejected alternative — invisible to agents, bypassable)
- Do not create wrapper scripts or aliases (rejected alternative — user-local, not agent-driven)
- Do not retroactively detect dangling commits (rejected alternative — detective, not preventive)
- Do not modify runtime application source code; changes are limited to skill definitions (`SKILL.md` files)
- Do not auto-merge PRs or modify remote repository state beyond verification

## User Stories

- As an AET user running `aet-ship`, I want the skill to verify my branch is actually on `origin/main` before deleting it, so that I don't accidentally lose work.
- As an AET user running `aet-pipeline-implement`, I want the pipeline to distinguish between "docs synced" and "merged to main," so that branch deletion only happens when it's truly safe.
- As an AET user running `aet-work` in AFK mode, I want the queue to verify the previous task's merge status before starting the next task, so that downstream tasks don't fail or re-implement code that isn't on `main` yet.

## Acceptance Criteria

- [ ] `aet-ship/SKILL.md` contains a merge verification step that runs `git merge-base --is-ancestor HEAD origin/main` before branch deletion
- [ ] `aet-ship/SKILL.md` prints a clear, actionable warning and exits non-zero if the check fails
- [ ] `aet-pipeline-implement/SKILL.md` defines a `merged` stage in its stage table
- [ ] `aet-pipeline-implement/SKILL.md` includes post-ship verification procedure that updates plan stage to `merged` and work queue `merge_verified` on success
- [ ] `aet-work/SKILL.md` adds `merge_verified` and `merge_commit` fields to work queue schema
- [ ] `aet-work/SKILL.md` checks the previous task's `merge_verified` field before starting the next task
- [ ] Old work queues without `merge_verified` continue to function (treated as unverified, not broken)
- [ ] All three updated `SKILL.md` files remain under 400 lines
- [ ] `make validate` passes after all changes
- [ ] `make package` regenerates all `.skill` files without errors

## Technical Notes

- Verification command to use across all skills: `git merge-base --is-ancestor HEAD origin/main`
- The `merged` stage in `aet-pipeline-implement` sits after `synced` in the progression: `synced` → `merged`
- `aet-work` work-queue JSON schema addition is additive; existing queues without the field are gracefully handled
- Each skill change is independent enough to be its own plan, but ordered by dependency: `aet-ship` first, then `aet-pipeline-implement`, then `aet-work`
- Changes are documentation-only (SKILL.md updates) — no application runtime code is modified
- An ADR should document why toolkit-level enforcement is preferred over project-level `AGENTS.md` rules

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SKILL.md line count exceeds 400 | Medium | Low | Move deep detail to `references/`; the changes are ~20-25 lines per skill |
| `git merge-base` behavior differs across git versions | Low | Low | Use standard plumbing command available since git 1.5+ |
| Users on non-`main` default branches | Medium | Medium | Use `origin/main` explicitly as documented convention; if projects use `master`, they can override in AGENTS.md |
| Old work queues break on new field | Low | High | Treat missing `merge_verified` as `null` (unverified), not an error |

## Open Questions

1. Should the verification target be configurable (e.g., `origin/main` vs `origin/master` vs a custom base branch)?
2. Should `aet-ship` attempt to auto-detect the default remote base branch instead of hardcoding `origin/main`?
3. Should `aet-work` automatically run merge verification on a stale task, or just halt and prompt the user?

---
*Stage: scope-validated*
*Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)*

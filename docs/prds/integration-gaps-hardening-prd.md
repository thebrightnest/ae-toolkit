# PRD: Integration Gaps Hardening

## Overview

The P3-REM retro (2026-05-20) revealed that five feature branches were implemented, tested, and marked "done" in the work queue — but never merged to `main`. Branch-safety work (bs-01..bs-03) already added reactive merge verification to `aet-ship`, `aet-pipeline-implement`, and `aet-work`. This PRD closes the remaining gaps: missing merge steps in plan templates, lack of proactive branch-drift detection, and no safety checks for symbol removal or orphaned API calls during migrations.

## Goals

- Every plan produced from the toolkit template includes "merge to main and verify" as an explicit, final, non-optional task
- `aet-work` can proactively detect tasks marked `done` whose branches are not ancestors of `origin/main`
- `aet-review` catches removed symbols still referenced elsewhere before the PR ships
- `aet-qa` documents a procedure to detect API/bridge calls that lack corresponding backend handlers
- All changes are additive — existing skills and queues continue to function

## Non-Goals

- Do not modify runtime application code in downstream projects
- Do not add CI infrastructure or git hooks (toolkit provides skill guidance, not project-specific automation)
- Do not retroactively fix the P3-REM branches (they are already resolved)
- Do not change the core branch-safety verification command (`git merge-base --is-ancestor HEAD origin/main`)

## User Stories

- As an AET user creating a plan, I want the template to include merge-to-main as a task, so I don't forget it.
- As an AET user running `aet-work status`, I want to see any "done" tasks that are not actually on `main`, so integration debt surfaces before the next task starts.
- As an AET user cleaning up IPC/API shims, I want `aet-review` to warn me if I removed a symbol that is still referenced, so I don't break the renderer.
- As an AET user migrating renderer calls, I want `aet-qa` to flag calls with no backend handler, so I don't ship dead code.

## Acceptance Criteria

- [ ] `.agents/templates/plan-template.md` includes "Merge to main and verify" as the final task in the task list
- [ ] `aet-work/SKILL.md` defines a `drift-check` command that lists tasks with status `done` or `merged` where `git merge-base --is-ancestor <branch> origin/main` fails
- [ ] `aet-work/SKILL.md` documents `completed_at` and `merged_at` timestamp fields in the work-queue schema
- [ ] `aet-review/SKILL.md` adds a "Removal Safety" lens: when diff deletes symbols from bridge/API/registry files, grep the tree for remaining references
- [ ] `aet-qa/SKILL.md` documents a check for orphaned API/bridge calls (renderer calls without corresponding backend handler)
- [ ] All updated `SKILL.md` files remain under 400 lines
- [ ] `make validate` passes after all changes
- [ ] `make package` regenerates all `.skill` files without errors

## Technical Notes

- **Plan template**: Add a `[ ] Merge branch to main and verify: git merge-base --is-ancestor HEAD origin/main` line to the default task list
- **Drift detection**: For each task in the queue with status `done` or `merged`, attempt `git merge-base --is-ancestor <branch> origin/main`. If the branch name is unknown, fall back to checking if the plan file's commits are on `main`. Report unmerged tasks with branch names and plan file paths.
- **Timestamps**: `completed_at` is set when status moves to `done` or `merged`. `merged_at` is set only when `merge_verified` becomes `true` (or during `post-ship-verify`). Both are ISO-8601 strings.
- **Removal safety lens**: Triggered when diff touches files matching `*Bridge*`, `*preload*`, `*handler*`, `*registry*`, `*shim*`, `*api*` (case-insensitive). Extract deleted function/constant names, then `grep -r` across `src/` or equivalent. Flag any matches.
- **Orphaned API check**: This is project-specific, so `aet-qa` should provide a generic procedure: grep renderer for API call patterns, list them, and require the user to confirm each has a corresponding backend handler. Do not hardcode `window.claudeApi` or similar project-specific names.

## Risks

| Risk                                           | Likelihood | Impact | Mitigation                                                                    |
| ---------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------- |
| `aet-work` line count exceeds 400              | Medium     | Low    | Move drift-check detail to `references/branch-drift-detection.md`             |
| `aet-review` line count exceeds 400            | Medium     | Low    | Move removal safety detail to `references/removal-safety-lens.md`             |
| Drift-check false positives on squashed merges | Medium     | Medium | Check `merge_commit` field first; if present and on main, skip ancestor check |
| Timestamp fields break old queues              | Low        | High   | Fields are optional; missing = null                                           |

## Open Questions

1. Should `drift-check` be a standalone command or integrated into `aet-work status`?
2. Should removal safety run on every review, or only when the diff exceeds a deletion threshold?
3. Should the orphaned API check live in `aet-qa` or `aet-review`?

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_

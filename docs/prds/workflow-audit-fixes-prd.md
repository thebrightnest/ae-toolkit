# PRD: Workflow Audit Fixes — Coverage Batch 2 Cleanup

## Overview

The Coverage Batch 2 (COV-\*) campaign exposed ten systemic workflow issues in the AE Toolkit's skills and orchestrator. These range from stale queue state and empty worktree leaks to pre-push hook timeouts and branch lifecycle mismanagement. This PRD defines a coordinated fix across `aet-work`, `aet-ship`, `aet-pipeline-implement`, and repository hooks to make the orchestration layer reliable enough for unattended multi-task runs.

## Goals

1. **Eliminate stale queue state** — worktree fields, done-without-merge, and orphaned branches are detected and repaired automatically.
2. **Prevent resource leaks** — empty worktrees, duplicated plan directories, and accumulated post-merge branch commits are blocked or cleaned up.
3. **Harden pipeline termination** — agents hitting step limits leave committed, formatted, pushed code, not uncommitted partial work.
4. **Standardize branch lifecycle** — branch naming, release-bump gating, and squash-merge cleanup are enforced by skill logic, not human discipline.
5. **Fix hook false-positives** — pre-push coverage gates skip branch deletions and do not timeout cleanup operations.

## Non-Goals

- Rewriting the orchestrator in a different language or runtime.
- Changing the `.skill` packaging format or zip-based distribution.
- Adding a new issue tracker integration or external queue backend.
- Modifying the core agent step-limit (100) itself — we work within it.
- Re-running or recovering the already-finished COV-\* tasks.

## User Stories

- As an agent operator running `aet-work run`, I want empty worktrees auto-removed so disk space does not leak across campaigns.
- As a task author, I want `done` to mean "verified on main" so I never lose unmerged commits.
- As a pipeline user, I want step-limit exhaustion to finish with `git commit --no-edit` instead of uncommitted files.
- As a release manager, I want `chore(release)` commits rejected on feature branches so CHANGELOG merge conflicts disappear.
- As a cleanup script, I want `git push origin --delete` to skip the coverage gate so branch deletion is not blocked by a 60-second test run.

## Acceptance Criteria

- [ ] `aet-work status` flags worktree fields that point to missing directories.
- [ ] `aet-work cleanup` removes worktrees with 0 commits ahead of main and clears the queue field.
- [ ] `aet-work` refuses to mark a task `done` unless `merge_verified: true` or an explicit `abandoned: true` reason is set.
- [ ] Queue schema supports `merged`, `done` (deprecated), and `abandoned` terminal statuses.
- [ ] Orchestrator symlinks (or read-only mounts) `docs/plans` and `docs/prds` into worktrees; no `docs/plans/plans/` duplication occurs.
- [ ] `aet-pipeline-implement` writes `.review-report.md`, `.qa-report.md`, `.security-*.md` to `/tmp/aet-reports/<task-id>/`.
- [ ] `aet-pipeline-implement` reserves the final 5 steps for lint-fix + commit + optional push when step budget is below 10.
- [ ] `aet-ship` deletes local AND remote feature branches after successful squash merge.
- [ ] Pre-push hook short-circuits when all pushed refs are deletions.
- [ ] Branch naming is enforced: either `<task-id>` or `<type>/<task-id>-<slug>`; the actual branch name is stored in the queue `branch` field.
- [ ] Pre-commit hook rejects `chore(release)` commits on non-main branches.
- [ ] `aet-ship` no longer bumps version; version release is a future skill.

## Technical Notes

- All changes are to Markdown skill instructions and shell scripts in the `aet-*` skill directories. No compiled code.
- The orchestrator logic lives in `scripts/.aet-work-orchestrator.sh` and is referenced by `aet-work/SKILL.md`.
- Queue schema changes must be backwards-compatible: old `done` entries continue to work but surface a warning.
- Symlink vs copy decision: prefer symlink for `docs/plans` and `docs/prds` into worktrees; if the filesystem or OS prevents it, fall back to copy-with-read-only-flag.
- Step-limit reservation is advisory — the skill instructions tell the agent to monitor its own step count, not a runtime-enforced hard gate.
- Pre-push hook change is a repo-level `.git/hooks/pre-push` update (or `.githooks/` if the project uses that).

## Open Questions

1. Should the orchestrator delete the branch immediately after squash merge, or reset it to `main` and leave it for human inspection?
2. Is `/tmp/aet-reports/` acceptable on all target OSes, or should we use a platform-agnostic temp directory?
3. Do we need a migration script for the 39 historical tasks with stale worktree fields, or is `aet-work cleanup` sufficient?
4. Should `aet-ship` also delete the remote branch at the PR hosting service (GitHub/GitLab) via API, or is `git push origin --delete` sufficient?

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_

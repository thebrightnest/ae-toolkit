# Retro: PR Scope Control in aet-work / aet-ship

## What happened

On 2026-06-15, eight PRs opened by `aet-ship` contained ~220 changed files each. The actual task scopes were 5–26 files. The extra files came from:

1. Worktrees branched from the parent session branch, not `origin/main`.
2. Local `main` being 62 commits ahead of `origin/main`.
3. `aet-ship` opening PRs against the stale `origin/main` without rebasing.
4. E28-06, a stacked branch, opened against `main` instead of its parent `e28-05`.

## Why scope checks did not catch it

- `aet-ship` had no explicit scope audit.
- Stacked-branch detection used local `main`, which masked the real base because local `main` was ahead.
- The orchestrator trusted the current HEAD as the worktree base, so every worktree inherited the parent session's context.

## Changes made

### aet-work

- `create_worktree()` now fetches `origin/main` and creates the worktree from `origin/main`.
- Existing branches with a wrong merge-base are deleted and recreated.
- The project-specific `app/node_modules` symlink was removed; a generic AE Toolkit skill cannot assume a frontend layout.

### aet-ship

- PR base is computed against `origin/main`, not local `main`.
- Independent branches are rebased onto `origin/main` before opening the PR; conflicts stop the pipeline.
- Stacked branches open PRs against their nearest named ancestor feature branch.
- A scope-audit section is added to the PR body, flagging known global files such as `.agents/work-queue.json` and unrelated plan/PRD files.

### Guardrails and reference

- Added a one-line guardrail to `AGENTS.md` requiring `origin/main`-based worktrees and rebases.
- Created `.agents/reference/worktree-ship-hygiene.md` as the canonical rule set.

## Lessons

- **Local `main` is not authoritative.** Always use `origin/main` for base calculations in automated shipping.
- **A generic toolkit cannot carry project-specific conveniences.** The `app/node_modules` symlink fixed one project but would be wrong or misleading in others.
- **Scope audits should be warnings, not blockers.** A hard stop on heuristics creates false positives; surfacing the audit in the PR body lets reviewers decide.
- **Stacked branches need explicit base detection.** Using `origin/main` as the reference makes the parent branch discoverable even when local `main` is dirty or ahead.

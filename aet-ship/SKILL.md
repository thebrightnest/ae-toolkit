---
name: aet-ship
description: Pre-merge validation gate with bisectable commits, changelog generation, and PR creation. Use when code is reviewed and ready to merge. Fully non-interactive except for merge conflicts, test failures, and version bump decisions. Triggers on requests like "ship this," "prepare PR," or "merge ready."
---

# aet-ship

Pre-merge validation for agentic engineering. The final gate before code lands.

## When to Use

- Code has been implemented and reviewed
- You're ready to open or update a PR
- As the final step of the PIV loop

## Shared Preamble

Before executing any command in this skill, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — any `docs/plans/*.md` modified in last 7 days
- `LAST_PIV` — date of last completed plan-implement-validate cycle (from git log if available)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

## Commands

### `ship`

Run the pre-merge validation gate.

**Procedure:**

1. **Sync with main** — pull latest main, attempt trivial merge conflict resolution
2. **Stacked branch detection** — run `git merge-base HEAD main` and compare to `git rev-parse main`. If they differ, the branch was not branched directly from main's current tip — treat as stacked.

   - Identify the parent branch by scanning `git log --oneline --decorate main..HEAD` for the nearest named ancestor (the last commit decorated with a non-HEAD, non-remote ref).
   - Still create the PR against the parent branch — that is correct at creation time.
   - Prepend a `⚠️ STACKED PR` section to the PR body:

     ```
     ⚠️ STACKED PR — base is `[parent-branch]`, not main.
     After `[parent-branch]` merges to main, run:
       git rebase main && git push --force-with-lease && gh pr edit --base main
     before merging this PR.
     ```

   - Print a terminal stop-note after PR creation:

     ```
     ⚠️  STACKED PR: this PR targets [parent-branch], not main.
         After [parent-branch] merges, rebase onto main and update the base before merging.
     ```

   - **Do not auto-rebase. Do not auto-update the base.** Both are irreversible and can silently misresolve conflicts.

3. **Run test suite** — unit, integration, type-check, lint. Must all pass.
4. **Coverage audit** — check coverage didn't drop below threshold. Flag if it did.
5. **Plan completion check** — verify all tasks in `docs/plans/{ticket}-plan.md` are addressed
6. **Run `aet-review`** — staff-level code review on the diff
7. **Run `aet-cso`** — security audit if the diff touches auth, data, API, or dependencies
8. **Split commits** — ensure each commit is bisectable (one logical change). Split if needed.
9. **Generate CHANGELOG** — add entry based on commit messages and plan.md summary
10. **Bump VERSION** — auto-bump patch. Stop for human decision on MINOR/MAJOR.
11. **Push and open PR** — push branch, create PR with description linking plan.md and PRD

12. **Merge Verification** — after the PR is created and the user indicates it has been merged:

    1. Run `git fetch origin`

    2. **Merge Strategy Detection** (Step 12a):

       - Run: `git merge-base --is-ancestor HEAD origin/main`
       - If exit 0: regular merge detected. Record `merge_strategy: regular` and continue to Step 13.
       - If exit 1: possible squash merge. Run secondary verification:

         ```bash
         PR_NUMBER=$(gh pr view --json number --jq '.number')
         MERGE_COMMIT=$(gh pr view $PR_NUMBER --json mergeCommit --jq '.mergeCommit.oid')
         git merge-base --is-ancestor $MERGE_COMMIT origin/main
         ```

         - If exit 0: squash merge verified. Record `merge_commit: $MERGE_COMMIT` and `merge_strategy: squash`. Continue to Step 13 with force-delete.
         - If exit 1: verification failed. STOP.

       - If `gh` is unavailable or the PR has no mergeCommit data, fall back to diff-based verification (see [references/squash-merge-handling.md](references/squash-merge-handling.md)).

    3. If verification fails:

       - **STOP** and print:

         ```
         ⚠️  MERGE VERIFICATION FAILED
             This branch's commits are NOT ancestors of origin/main.
             Possible causes:
             - PR was merged locally but not pushed
             - PR targeted a different base branch
             - A git reset --hard origin/main discarded the merge
             - PR was squash-merged and the squash commit could not be verified

             DO NOT DELETE THIS BRANCH until the merge is confirmed on origin/main.
         ```

       - Offer to open the PR in the browser for manual verification
       - Exit with non-zero status

    4. If verification passes:

       - Print: `✅ Merge verified on origin/main`
       - Update `.agents/work-queue.json` with the merge result:

         ```json
         {
           "merge_commit": "<commit-sha>",
           "merge_verified": true,
           "merge_strategy": "regular|squash"
         }
         ```

       - Proceed to branch deletion (Step 13)

13. **Safe Branch Deletion** — only run if merge verification passed:
    - Regular merge: `git branch -d <branch>`
    - Squash merge: `git branch -D <branch>` (force delete; original commits are not ancestors)
    - Print: `✓ Branch <branch> safely deleted.`

**Stop conditions** (requires human intervention):

- Merge conflicts that can't be auto-resolved
- Test failures
- Coverage drop below threshold
- `aet-cso` fail (Critical/High findings)
- MINOR or MAJOR version bump needed
- Merge verification failure (commits not on origin/main)

**Output:**

- Clean branch with bisectable commits
- PR with linked plan.md and PRD
- CHANGELOG entry
- Version bump
- Merge verification status
- Safe branch deletion confirmation (if applicable)

## Key Principles

- **Non-interactive by default** — the gate runs without human input until something is wrong
- **Composable** — invokes `aet-review` and `aet-cso` rather than duplicating their logic
- **Bisectable commits** — one logical change per commit, enforced at process level
- **Auto-generated artifacts** — CHANGELOG and VERSION bump are mechanical, not human work
- **Merge verification is a hard gate** — commits must be ancestors of `origin/main` before any branch deletion
- **Shipping is not the end** — post-deploy monitoring (`canary`) closes the loop

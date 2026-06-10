# Plan: aet-ship Squash-Merge Core Support

## Context

- PRD: `docs/prds/aet-ship-squash-merge-support-prd.md`
- Existing skill: `aet-ship/SKILL.md` (current merge verification uses `git merge-base --is-ancestor HEAD origin/main`)
- Related ADR: `docs/adr/003-toolkit-level-branch-safety.md`

## Tasks

1. **Add Merge Strategy Detection to `aet-ship/SKILL.md`** — M

   Insert a new step between the existing Step 12 (Merge Verification) and Step 13 (Safe Branch Deletion):

   ```
   12a. **Merge Strategy Detection** — after `git fetch origin`, run:
        `git merge-base --is-ancestor HEAD origin/main`

        - If exit 0: regular merge. Continue to Step 13 with `git branch -d`.
        - If exit 1: possible squash merge. Run secondary verification:
          `PR_NUMBER=$(gh pr view --json number --jq '.number')`
          `MERGE_COMMIT=$(gh pr view $PR_NUMBER --json mergeCommit --jq '.mergeCommit.oid')`
          `git merge-base --is-ancestor $MERGE_COMMIT origin/main`

          - If exit 0: squash merge verified. Continue to Step 13 with `git branch -D`.
          - If exit 1: STOP and print the existing merge verification failure message.
        - If `gh` is unavailable or the PR has no mergeCommit data, fall back to
          diff-based verification (see references/squash-merge-handling.md).
   ```

   Update Step 13 to reference the detected merge strategy:

   ```

   13. **Safe Branch Deletion** — only run if merge verification passed:
       - Regular merge: `git branch -d <branch>`
       - Squash merge: `git branch -D <branch>` (force delete; original commits are not ancestors)
   ```

2. **Create `aet-ship/references/squash-merge-handling.md`** — S

   Document the diff-based fallback heuristic for non-GitHub remotes or when `gh` fails:

   - How to compute branch diff (`git diff merge-base..HEAD`)
   - How to search recent `origin/main` commits for matching diff
   - Limitations and when to halt for manual verification

3. **Add squash-merge example to `aet-ship/examples/`** — S

   Create `squash-merge-example.md` showing:

   - The ancestry check failing
   - The GitHub API verification succeeding
   - The force-delete command being used
   - Work queue update with `merge_strategy: squash`

4. **Update work queue schema note in `aet-ship/SKILL.md`** — S

   In the merge verification section, document that the work queue entry should include:

   ```json
   {
     "merge_commit": "<squash-commit-sha>",
     "merge_verified": true,
     "merge_strategy": "squash"
   }
   ```

## Dependencies

- Task 1 blocks Task 4 (work queue schema note references the detection logic)
- Tasks 2 and 3 are independent; run after Task 1 for clarity

## Validation Steps

- [ ] `aet-ship/SKILL.md` contains Step 12a (Merge Strategy Detection)
- [ ] Regular merge path still uses `git merge-base --is-ancestor HEAD origin/main`
- [ ] Squash merge path uses `gh pr view` to get mergeCommit and verifies it on origin/main
- [ ] Step 13 uses `-d` for regular merge and `-D` for squash merge
- [ ] `aet-ship/SKILL.md` remains under 400 lines
- [ ] `make validate` passes
- [ ] `make package` regenerates `.skill` files without errors

## Rollback Plan

Revert `aet-ship/SKILL.md` and delete the new `references/` and `examples/` files. Skill files are plain markdown — no runtime dependencies.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_

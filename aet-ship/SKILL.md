---
name: aet-ship
description: Pre-merge validation gate with bisectable commits, commit-message conventions, and PR creation. Use when code has been implemented and reviewed, you're ready to open or update a PR, or as the final step of the PIV loop. Triggers on requests like "ship this," "prepare PR," or "merge ready."
---

# aet-ship

Pre-merge validation for agentic engineering. The final gate before code lands.

## When to Use

- Code has been implemented and reviewed
- You're ready to open or update a PR
- As the final step of the PIV loop

## What This Skill Does NOT Do

- Does not update project-level `CHANGELOG.md` or `PRODUCT.md` (use `aet-release-prep` for release documentation)
- Does not decide when to cut a release or bump version (use `aet-release-prep` after merging)
- Does not publish artifacts or create git tags

## Shared Preamble

Before executing any command in this skill, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — any `docs/plans/*.md` modified in last 7 days
- `LAST_PIV` — date of last completed plan-implement-validate cycle (from git log if available)
- `ACTIVE_PRD_STAGE` — current `*Stage:*` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:*` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

## Commands

### `ship`

Run the pre-merge validation gate.

**Procedure:**

1. **Fetch origin and determine PR base**

   All base calculations use `origin/main`, not local `main`, so a stale or ahead local `main` cannot leak into the PR diff.

   1. Run `git fetch origin`
   2. Compute:

      ```bash
      merge_base=$(git merge-base HEAD origin/main)
      origin_main=$(git rev-parse origin/main)
      ```

   3. If `merge_base == origin_main`:
      - The branch is independent. Set `pr_base="origin/main"`.
   4. Else:

      - The branch is stacked. Find the nearest named ancestor:

        ```bash
        git log --oneline --decorate --ancestry-path "$merge_base"..HEAD
        ```

      - Exclude `HEAD` and remote refs. The last commit decorated with a local branch ref is the parent branch.
      - Set `pr_base=<parent-branch>`.

2. **Rebase independent branches onto `origin/main`**

   Only independent branches need to be rebased. Stacked branches keep their parent base.

   - If `pr_base == "origin/main"` and `merge_base != origin_main`:

     - The branch is independent but not based on the current `origin/main`.
     - Attempt:

       ```bash
       git rebase --onto origin/main "$merge_base" "$(git branch --show-current)"
       ```

     - If conflicts occur, **STOP** and print:

       ```
       ⛔ Rebase onto origin/main produced conflicts.
          Resolve them manually, then run aet-ship again.
       ```

     - Do not proceed until the rebase is clean.

   - If `pr_base` is a feature branch, do not rebase onto `origin/main`.

3. **Ensure clean working tree**

   Check `git status --short`. If there are uncommitted changes, stop and ask whether to stash, commit, or abort.

4. **Run test suite** — unit, integration, type-check, lint. Must all pass.

5. **Coverage audit** — check coverage didn't drop below threshold. Flag if it did.

6. **Plan completion check** — verify all tasks in `docs/plans/{ticket}-plan.md` are addressed

7. **Stage-aware review / CSO gate**

   Read the plan.md footer `*Stage:*`. The implementation pipeline (`aet-work run` / `run-one`) already advances plans through `reviewed` → `secure` → `synced`, so `aet-ship` must not duplicate that work.

   - If stage is `synced` or `secure`: skip both `aet-review` and `aet-cso`.
   - If stage is `reviewed`: run `aet-cso` only if the diff touches auth, data, API, or dependencies.
   - If stage is `qa-complete` or earlier: run `aet-review`, then run `aet-cso` if the diff touches auth, data, API, or dependencies.

   For each skipped step, print: `⏭️ Skipping {skill}: plan stage is already {stage}.`

8. **Critical-class `aet-verify` evidence gate** — if the active plan's `*Work class:*` is `critical`, require `aet-verify` evidence attached:

   - Look for an evidence file at `.agents/verify/{ticket}-evidence.md` (or `.agents/verify/{ticket}-evidence/` if multiple captures)
   - Evidence must include: mode used (foundation/feature/reproduction), command/output/screenshot, timestamp, and verifier signature (agent session or human)
   - If no evidence is attached: **STOP** and print:

     ```
     ⛔ Pipeline paused at aet-ship.
     Critical-class task requires aet-verify evidence.
     Attach evidence at .agents/verify/{ticket}-evidence.md before shipping.
     ```

   - Do not open the PR until evidence is present

9. **Scope audit**

   Run `git diff "$pr_base" --name-only` and check for files that are unlikely to belong to this task:

   - `docs/plans/*.md` or `docs/prds/*.md` files that are not this task's own plan or associated PRD

   Build a `Scope audit` section for the PR body:

   ```
   ## Scope audit

   Files changed outside this task's expected scope:

   - docs/plans/OTHER-01-plan.md
   - .agents/work-queue.json
   ```

   If no out-of-scope files are found, omit the section or print `✅ Scope audit: no unexpected files detected.`

   This is a warning, not a hard gate. Continue opening the PR so the reviewer can see the audit.

10. **Split commits** — ensure each commit is bisectable (one logical change). Split if needed.

11. **Generate CHANGELOG** — add entry based on commit messages and plan.md summary

12. **Push branch**

    - If the branch was rebased in step 2, push with force-with-lease:

      ```bash
      git push --force-with-lease
      ```

    - Otherwise, push normally:

      ```bash
      git push
      ```

13. **Open PR** against the base determined in step 1:

    ```bash
    gh pr create --base "$pr_base" ...
    ```

    PR body must include:

    - Links to plan.md and PRD
    - Scope audit section (from step 9) if any files were flagged
    - A stacked-PR warning if `pr_base` is not `origin/main`

    **Stacked PR warning:**

    If `pr_base` is a feature branch, prepend to the PR body:

    ```
    ⚠️ STACKED PR — base is `[parent-branch]`, not main.
    After `[parent-branch]` merges to main, run:
      git rebase main && git push --force-with-lease && gh pr edit --base main
    before merging this PR.
    ```

    Print a terminal stop-note after PR creation:

    ```
    ⚠️  STACKED PR: this PR targets [parent-branch], not main.
        After [parent-branch] merges, rebase onto main and update the base before merging.
    ```

    > **Version bump is not handled here.** Release versioning is the responsibility of a future `aet-release` skill. Do not commit `chore(release)` or VERSION changes on feature branches.

14. **Merge Verification and Terminal Closure** — `aet-ship` is the single owner of task closure after merge verification. After the PR is created and the user indicates it has been merged:

    First, confirm the `ship` helper is available:

    ```bash
    command -v ship
    ```

    If this fails, **STOP** and print:

    ```
    ⚠️  ship is not on PATH.
        AET skill binaries must be installed before merge verification can close the task.
        The installer lives in the aet-setup skill, so aet-setup must be installed.
        Install options:
          - Run install-aet-binaries from the installed aet-setup skill
            (~/.agents/skills/aet-setup/bin/install-aet-binaries)
          - From this repo: make install-skills
          - Manually: add the skill bin directories (e.g. ~/.agents/skills/aet-ship/bin) to PATH.
    ```

    Then run the closure command:

    ```bash
    ship <task_id> <plan_file>
    ```

    This command:

    - Runs `git fetch origin`.
    - Detects a regular merge when the branch tip is an ancestor of `origin/main`.
    - Detects a squash merge via `gh pr view <branch> --json mergeCommit` and verifies the SHA is an ancestor of `origin/main`.
    - Falls back to diff-equivalence detection against recent `origin/main` commits (see [references/squash-merge-handling.md](references/squash-merge-handling.md)).
    - On success:
      - Updates the plan file YAML frontmatter `status` to `merged` — the durable source of truth.
      - Updates the plan file footer `*Stage:*` to `merged` and `*Next step:*` to `None`.
      - Records `merge_commit`, `merge_strategy`, `status: merged`, and `merged_at` in `.agents/work-queue.json`.
      - Appends a closure record to `.agents/work-history.jsonl`.
      - Removes the task from `.agents/work-queue.json`.
    - On failure, exits non-zero without mutating the plan, queue, or history.

    If the closure command fails:

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

    - Offer to open the PR in the browser for manual verification.
    - Exit with non-zero status.

15. **Safe Branch Deletion** — only run if the closure command succeeded:
    - Regular merge: `git branch -d <branch>`
    - Squash merge: `git branch -D <branch>` (force delete; original commits are not ancestors)
    - Delete the remote branch: `git push origin --delete <branch>`
    - Print: `✓ Branch <branch> safely deleted (local and remote).`

**Stop conditions** (requires human intervention):

- Rebase conflicts onto `origin/main`
- Merge conflicts that can't be auto-resolved
- Test failures
- Coverage drop below threshold
- `aet-cso` fail (Critical/High findings, only if CSO ran)
- Merge verification failure (commits not on origin/main)

**Output:**

- Clean branch with bisectable commits
- PR with linked plan.md and PRD
- PR scope audit section
- CHANGELOG entry
- Merge verification status
- Safe branch deletion confirmation (if applicable)

## Key Principles

- **Non-interactive by default** — the gate runs without human input until something is wrong
- **Composable** — invokes `aet-review` and `aet-cso` rather than duplicating their logic
- **Stage-aware** — respects the plan footer; does not rerun review or CSO already completed by the implementation pipeline
- **Bisectable commits** — one logical change per commit, enforced at process level
- **Auto-generated artifacts** — CHANGELOG entry is mechanical, not human work
- **Merge verification is a hard gate** — commits must be ancestors of `origin/main` before any branch deletion
- **Shipping is not the end** — post-deploy monitoring (`canary`) closes the loop

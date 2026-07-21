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

1. **Run the pre-merge gate in code**

   Steps 1–9 of the pre-merge gate (fetch/rebase, clean-tree check, test suite, coverage audit, plan-completion check, stage-aware review/CSO skip logic, critical-class verify-evidence gate, and scope audit) are implemented in `aet ship gate`. Run:

   ```bash
   aet ship gate <plan_file>
   ```

   If the gate reports a stop condition, resolve it before continuing.

2. **Open the PR in code**

    The remaining pre-PR steps (bisectable-commit check, CHANGELOG entry generation, push, and PR creation) are implemented in `aet ship open`. Run:

    ```bash
    aet ship open <plan_file>
    ```

    If `aet ship open` reports a stop condition (gate failure, monolithic commit, release-guard violation, push error, or PR creation error), resolve it before continuing.

    > **Version bump is not handled here.** Release versioning is the responsibility of a future `aet-release` skill. Do not commit `chore(release)` or VERSION changes on feature branches.

3. **Merge Verification and Terminal Closure** — `aet-ship` is the single owner of task closure after merge verification. **The PR merge is the human's decision**; the skill only runs after the human indicates the PR has been merged:

    First, confirm the `ship` helper is available:

    ```bash
    command -v ship
    ```

    If this fails, **STOP** and print:

    ```
    ⚠️  ship is not on PATH.
        AET skill binaries must be installed before merge verification can close the task.
        The installer lives in the aet-work skill, so aet-work must be installed.
        Install options:
          - Run `aet install`
          - From this repo: `make install-skills`
    ```

    Then run the closure command:

    ```bash
    ship record-merge <task_id> <plan_file>
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

4. **Safe Branch Deletion** — only run if the closure command succeeded:
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

- **Non-interactive by default** — the validation gate runs without human input until something is wrong; the merge action itself is the human's decision and is never performed by the agent
- **Composable** — invokes `aet-review` and `aet-cso` rather than duplicating their logic
- **Stage-aware** — respects the plan footer; does not rerun review or CSO already completed by the implementation pipeline
- **Bisectable commits** — one logical change per commit, enforced at process level
- **Auto-generated artifacts** — CHANGELOG entry is mechanical, not human work
- **Merge verification is a hard gate** — commits must be ancestors of `origin/main` before any branch deletion
- **Shipping is not the end** — post-deploy monitoring (`canary`) closes the loop

# Workflow Audit — 2026-06-01

## Context

During cleanup of the Coverage Batch 2 (COV-\*) worktrees and historical remote branches, several systemic workflow issues were identified. These are patterns that could be prevented or automated by upgrading the aet skills and orchestrator.

---

## Findings

### 1. Squash-Merged Branches Accumulate Post-Merge Commits

**Problem:** Multiple branches (TEST-5, E2E-critical-journeys, KNW-T1, TEST-3) were squash-merged into `main`, but subsequent commits (plan stage updates, review reports, release bumps) were added to the **same branch**. This leaves the branch with commits "ahead of main" even though the feature work is merged.

**Impact:**

- Branches appear to have unmerged work when inspected with `git rev-list --count main..branch`
- Cleanup is ambiguous — should the branch be deleted or does it contain real fixes?
- E2E-critical-journeys had a `chore(release): bump version to 1.18.33` commit on the feature branch

**Evidence:**

- `origin/TEST-5`: 4 commits ahead (plan syncs, QA reports, merge-from-main)
- `origin/feat/E2E-critical-journeys`: 8 commits ahead (plan syncs, review report, release bump)
- `origin/feat/TEST-3-core-services-backfill`: 7 commits ahead (plan sync, release bump)

**Recommendation:**

- After a successful squash merge, **aet-ship** or **aet-work** should either:
  - Delete the branch immediately, or
  - Block further commits to the merged branch by resetting it to main
- Release bumps (`chore(release)`) should be gated to `main` branch only via pre-commit or CI

---

### 2. "Done" Tasks Without Merge Verification

**Problem:** Tasks marked `done` in the work queue but with `merge_commit: null` and no `merge_verified: true`. It is impossible to tell from the queue alone whether the work was merged, abandoned, or parked.

**Impact:**

- TEST-10 and TEST-10c have real unmerged commits on remote branches that could be lost
- The `done` status implies completion, but main does not contain the code

**Evidence:**

- `TEST-10`: status `done`, branch `null`, 1 commit ahead of main (`taskHandler.test.ts` +707 lines)
- `TEST-10c`: status `done`, branch `TEST-10c`, 1 commit ahead of main (adds dompurify, ChatMessageBubble rich content)

**Recommendation:**

- **aet-work** should refuse to mark a task `done` unless:
  - `merge_verified: true`, OR
  - An explicit `"abandoned": true` flag is set with a reason
- The `done` status should be renamed to `merged` (when on main) or `closed` (when abandoned)

---

### 3. Orchestrator Leaves Empty Worktrees Behind

**Problem:** The `aet-work run` orchestrator creates a git worktree for every unblocked task. If the agent process fails early or hits a step limit, the worktree exists but contains **zero commits** ahead of main.

**Impact:**

- 7 empty worktrees were found: COV-M1, COV-M2, COV-M3, COV-M4, COV-R3, COV-R4, COV-R6
- Each worktree is a full git checkout (~2GB disk usage total)
- The queue's `worktree` field was `null` for these, so there was no tracked linkage

**Evidence:**

```
COV-M1: 0 commits ahead of main
COV-M2: 0 commits ahead of main
...
```

**Recommendation:**

- `aet-work cleanup` should detect worktrees with 0 commits ahead of main and auto-remove them
- The orchestrator should remove the worktree if the spawned agent exits without creating any commits

---

### 4. Agent Step Limit Causes Uncommitted Partial Work

**Problem:** COV-R5 failed because the `kimi` agent hit the 100-step limit during `aet-pipeline-implement`. The final step was a `git commit` that failed the pre-commit hook (Prettier formatting). The agent exited, leaving uncommitted changes in the worktree.

**Impact:**

- Human intervention required to finish formatting and commit
- The queue marks the task `failed` even though the actual feature work (tests) was complete
- Risk of losing work if the worktree is cleaned up before manual rescue

**Evidence:**

- COV-R5: `❌ Task failed with exit code 1` — `Max number of steps reached: 100`
- Uncommitted files: `.review-report.md`, test files, duplicate `docs/plans/plans/` directory

**Recommendation:**

- `aet-pipeline-implement` should reserve the final ~5 steps for:
  - `make check` / `npm run lint` / `npx prettier --write`
  - `git add` + `git commit`
  - `git push` (optional)
- If the step limit is approaching, the agent should enter a "terminal mode" that only allows git/commit actions
- Alternatively, increase the step limit for pipeline-implement tasks (currently 100)

---

### 5. Path Duplication When Orchestrator Copies Plans into Worktrees

**Problem:** The orchestrator copies `docs/plans` and `docs/prds` into the worktree so agents can reference them. However, agents sometimes write updated plan files to `docs/plans/plans/` (double-nested), creating duplicated directories.

**Impact:**

- Pre-commit hook fails with Prettier formatting warnings on duplicated files
- The agent wastes steps creating and trying to commit files in the wrong location
- Risk of committing duplicate plans into the repo

**Evidence:**

- COV-R1, COV-R2, COV-R5 all had `docs/plans/plans/` directories with copies of all plan files
- COV-R5's commit attempt failed because `docs/plans/plans/COV-R5-RichTextEditor-Launcher.md` was incorrectly staged

**Recommendation:**

- The orchestrator should **symlink** `docs/plans` and `docs/prds` into the worktree instead of copying
- If copying is required, the orchestrator should set the directory read-only or add a `.gitignore` inside the worktree to prevent the agent from staging copied plans

---

### 6. Agent Artifacts Risk Being Committed

**Problem:** The pipeline generates `.review-report.md`, `.qa-report.md`, `.security-audit.md` in the repo root during execution. These are process artifacts, not production code.

**Impact:**

- COV-R5 staged `.review-report.md` in its commit attempt
- These files trigger pre-commit checks (Prettier, secrets scan) unnecessarily
- If committed, they pollute the git history

**Evidence:**

- COV-R1 worktree contained `.review-report.md`, `.qa-report.md`, `.security-audit.md`, `.security-report.md`
- COV-R5 commit failed partly because `.review-report.md` was staged and Prettier flagged it

**Recommendation:**

- **aet-pipeline-implement** should write all reports to a temporary directory outside the repo (e.g., `/tmp/aet-reports/<task-id>/`)
- Alternatively, add a `.gitignore` rule for `/.review-report.md`, `/.qa-report.md`, `/.security-*.md` at the repo root

---

### 7. Pre-Push Hook Timeout Blocks Branch Cleanup

**Problem:** Deleting remote branches with `git push origin --delete` triggers the pre-push hook, which runs the full test suite + coverage diff gate. This takes >60 seconds and times out background shell tasks.

**Impact:**

- First deletion attempt timed out after 60s
- Required `--no-verify` workaround to skip the hook
- The hook is irrelevant for branch deletions (no new code being pushed)

**Evidence:**

```
[pre-push] Running TypeScript type check...
[pre-push] Running coverage diff gate...
[coverage-gate] Running tests with coverage (this may take a minute)...
```

**Recommendation:**

- The pre-push hook should short-circuit and skip when **all pushed refs are deletions** (no new objects)
- Or: `aet-work cleanup` should use `--no-verify` automatically for branch deletion operations

---

### 8. Queue `worktree` Field Becomes Stale

**Problem:** 50 tasks in `.agents/work-queue.json` have a `worktree` field, but only 11 worktrees actually existed on disk. The rest were removed manually in previous sessions without updating the queue.

**Impact:**

- `aet-work status` reports tasks as having worktrees that don't exist
- The orchestrator's `handle_orphaned_in_progress` check relies on `worktree` accuracy

**Evidence:**

```python
Tasks tracking worktrees: 50
Actual worktrees on disk: 11
```

**Recommendation:**

- `aet-work status` should validate that tracked worktrees exist on disk and flag stale entries
- `aet-work cleanup` should clear the `worktree` field when it removes a worktree

---

### 9. Branch Naming Inconsistency Breaks Automation

**Problem:** Branches are named inconsistently: some match the task ID exactly (`COV-R1`, `BROWSER-1`), others use `feat/` prefixes (`feat/COV-T1-core-state-stores`), and others use `fix/` or `test/` prefixes.

**Impact:**

- Hard to correlate a remote branch with its queue task programmatically
- The orchestrator uses the task ID as the branch name, but historical branches don't follow this convention
- Cleanup scripts must maintain a mapping table

**Evidence:**

- `COV-R1` → branch `COV-R1` ✅
- `COV-T1` → branch `feat/COV-T1-core-state-stores` ❌
- `TEST-1` → branch `test/TEST-1-chat-handler-completion` ❌

**Recommendation:**

- **aet-work** should enforce branch naming: either always `<task-id>` or always `<type>/<task-id>`
- Store the actual branch name in the queue's `branch` field and use it for all git operations

---

### 10. Release Bumps on Feature Branches

**Problem:** Two feature branches contained `chore(release)` commits bumping the version and updating CHANGELOG.

**Impact:**

- `feat/E2E-critical-journeys`: `chore(release): bump version to 1.18.33 + changelog`
- `feat/TEST-3-core-services-backfill`: `chore(release): bump version to 1.18.35`
- These commits would create merge conflicts if the branch were ever merged/rebased
- Release bumps belong exclusively on `main`

**Recommendation:**

- Add a pre-commit or pre-push hook that rejects `chore(release)` commits on non-main branches
- Or: configure the release script to refuse running on feature branches

---

## Summary Table

| #   | Issue                              | Affected Tasks                                | Skill to Fix             |
| --- | ---------------------------------- | --------------------------------------------- | ------------------------ |
| 1   | Post-merge branch commits          | TEST-5, E2E-critical-journeys, KNW-T1, TEST-3 | `aet-ship`, `aet-work`   |
| 2   | `done` without merge verification  | TEST-10, TEST-10c                             | `aet-work`               |
| 3   | Empty worktrees left behind        | COV-M1–M4, COV-R3/4/6                         | `aet-work`               |
| 4   | Step limit aborts at commit        | COV-R5                                        | `aet-pipeline-implement` |
| 5   | Plan path duplication in worktrees | COV-R1, COV-R2, COV-R5                        | `aet-work`               |
| 6   | Artifact files risk commit         | COV-R1, COV-R5                                | `aet-pipeline-implement` |
| 7   | Pre-push hook blocks deletion      | All branch cleanup                            | Repo hooks               |
| 8   | Stale worktree fields in queue     | 39 historical tasks                           | `aet-work`               |
| 9   | Branch naming inconsistency        | COV-T1, TEST-1, etc.                          | `aet-work`               |
| 10  | Release bumps on features          | E2E-critical-journeys, TEST-3                 | Repo hooks, `aet-ship`   |

---

## Suggested Next Steps

1. **Update `aet-work`** to auto-remove empty worktrees and clear stale `worktree` fields
2. **Update `aet-pipeline-implement`** to reserve terminal steps for commit/push and write reports outside the repo
3. **Update `aet-ship`** to delete or reset branches after squash merge
4. **Update pre-push hook** to skip coverage gate when deleting branches
5. **Update queue schema** to distinguish `merged` vs `done` vs `abandoned`

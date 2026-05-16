# AET Toolkit Enhancement Report: Branch Safety in Agentic Pipelines

**Date:** 2026-05-16
**Author:** aet-evolve (auto-generated retro → system-evolve)
**Severity:** High — silent data loss
**Scope:** `aet-ship`, `aet-pipeline-implement`, `aet-work`

---

## 1. Problem Summary

Two completed feature branches (`feat/p3-t1-http-server-modernization` and `feat/UI-1`) were deleted after being "merged," but their commits never reached `origin/main`. The code was later discovered as dangling commits with no branch pointing to them.

**Impact:**

- ~20 hours of work temporarily "lost" (recovered via `git fsck` + merge)
- Downstream tasks (P3-T3 through P3-T6) were incorrectly blocked for days
- Work-queue reconstruction required manual git archaeology

---

## 2. Root Cause: The "Local Merge Trap"

The `aet-ship` skill creates a PR and pushes the branch, but **does not merge the PR or verify the merge landed on `origin/main`**. The human (or a subsequent pipeline step) merged locally, then ran `git reset --hard origin/main` during cleanup. Since `origin/main` didn't have the merge commits, the reset silently discarded them. Branches were then deleted under the assumption they were merged.

**The gap in the AET pipeline:**

```
aet-implement → aet-review → aet-ship → [MERGE GAP] → branch deleted
                                         ↑
                                    No verification that
                                    commits are on origin/main
```

`git branch -d <branch>` only checks if the branch is merged into **local `HEAD`**. It does not check `origin/main`. This is a footgun that every AET user will eventually hit.

---

## 3. Proposed Solution: Toolkit-Level Branch Safety

Instead of requiring every project to add a "Branch Cleanup Safety" rule to `AGENTS.md`, the toolkit skills should enforce branch safety automatically. Below are specific, minimal changes to three skills.

---

## 4. Skill-by-Skill Proposals

### 4.1 `aet-ship` — Add Merge Verification Gate

**Current behavior:** `ship` creates a PR, pushes the branch, and stops. It prints "PR created" and expects the human to merge.

**Proposed addition:** After PR creation, add a **merge verification step** that runs before any branch deletion:

````markdown
### `ship` — Step 12: Merge Verification (NEW)

After the PR is created and the user indicates it has been merged:

1. Run `git fetch origin`
2. Verify: `git merge-base --is-ancestor HEAD origin/main`
3. If the check fails:
   - **STOP** and print:

     ```
     ⚠️  MERGE VERIFICATION FAILED
         This branch's commits are NOT ancestors of origin/main.
         Possible causes:
         - PR was merged locally but not pushed
         - PR targeted a different base branch
         - A git reset --hard origin/main discarded the merge

         DO NOT DELETE THIS BRANCH until the merge is confirmed on origin/main.
     ```

   - Offer to open the PR in the browser for manual verification
   - Exit with non-zero status

4. If the check passes:
   - Print: `✅ Merge verified on origin/main`
   - Proceed to branch deletion (Step 13)

### `ship` — Step 13: Safe Branch Deletion (NEW)

Only run if Step 12 passed:

```bash
git merge-base --is-ancestor HEAD origin/main && git branch -d $(git branch --show-current)
```
````

**Rationale:** This is the exact moment where the pipeline transitions from "code is ready" to "code is on main." The toolkit should own this verification, not the human's memory or a project-specific AGENTS.md rule.

````

**Files to change:** `/Users/{user}/.claude/skills/aet-ship/SKILL.md`

---

### 4.2 `aet-work` — Queue-Level Branch Tracking

**Current behavior:** `aet-work` picks the next task from `.agents/work-queue.json` and runs `aet-pipeline-implement`. It does not track whether the branch from a previous task was properly merged before the next task starts.

**Proposed addition:** Add branch-state tracking to the work queue:

```json
{
  "id": "P3-T1",
  "status": "done",
  "branch": "feat/p3-t1-http-server-modernization",
  "merge_verified": "origin/main",
  "merge_commit": "c0f5677"
}
````

**Procedure addition for `aet-work`:**

```markdown
### Before Starting Next Task

1. Check the previous task's `merge_verified` field:
   - If `null` or missing: **STOP** and run `aet-ship` merge verification on the previous task's branch
   - If set to `"origin/main"`: proceed

2. If a task has `status: "done"` but `merge_verified: null`:
   - Print warning: `Previous task P3-T1 is marked done but not verified on origin/main. Running merge verification...`
   - Run verification. If it fails, halt the queue until resolved.
```

**Rationale:** In a sequential queue, downstream tasks often depend on upstream tasks being on `main`. If P3-T1 is "done" but not on `origin/main`, P3-T3 will fail or re-implement code. The queue runner should enforce this invariant.

**Files to change:** `/Users/{user}/.claude/skills/aet-work/SKILL.md`

---

### 4.3 `aet-pipeline-implement` — Pipeline Resume Safety

**Current behavior:** The pipeline reads the plan's stage (`tdd-complete`, `implemented`, etc.) and skips completed steps. It does not verify that the branch from a previously completed pipeline was merged to `origin/main`.

**Proposed addition:** Add a stage `merged` after `synced`:

```markdown
| Stage found | Start from                                              |
| ----------- | ------------------------------------------------------- |
| ...         | ...                                                     |
| `synced`    | Pipeline complete → suggest `aet-ship` → wait for merge |
| `merged`    | Fully complete → safe to delete branch                  |
```

**Procedure addition:**

```markdown
### Post-Ship Verification

After `aet-ship` completes and the user confirms the PR is merged:

1. Run `git fetch origin`
2. Verify: `git merge-base --is-ancestor HEAD origin/main`
3. If pass:
   - Update plan stage to `merged`
   - Update `.agents/work-queue.json` with `merge_verified: "origin/main"`
   - Safe to delete branch
4. If fail:
   - Keep plan stage at `synced`
   - **Do not delete branch**
   - Print actionable next steps
```

**Rationale:** The pipeline currently ends at `synced` (docs updated). But "synced" doesn't mean "on main." Adding a `merged` stage creates a hard gate that prevents branch deletion before remote verification.

**Files to change:** `/Users/{user}/.claude/skills/aet-pipeline-implement/SKILL.md`

---

## 5. Why This Belongs in the Toolkit, Not AGENTS.md

| Concern                    | AGENTS.md Rule                       | Toolkit Skill                                        |
| -------------------------- | ------------------------------------ | ---------------------------------------------------- |
| **Enforcement**            | Human must remember to run a command | Automatic gate — pipeline stops if check fails       |
| **Consistency**            | Every project writes its own version | One correct behavior across all AET projects         |
| **Discoverability**        | Buried in a file agents may not load | Active step in the skill the user is already running |
| **Error handling**         | "Oops, I forgot"                     | Pipeline halts with actionable message               |
| **Cross-project learning** | Per-project rules don't compound     | One fix improves every AET project simultaneously    |

The AGENTS.md rule we added today (`.agents/commands/branch-cleanup.md`) is a **project-level workaround**. It helps this specific project, but the next AET user on a different repo will hit the same bug. The fix belongs in `aet-ship`, `aet-work`, and `aet-pipeline-implement`.

---

## 6. Implementation Complexity

| Skill                    | Change                                      | Lines | Risk                                                       |
| ------------------------ | ------------------------------------------- | ----- | ---------------------------------------------------------- |
| `aet-ship`               | Add Steps 12–13                             | ~25   | Low — only adds verification, doesn't change existing flow |
| `aet-work`               | Add `merge_verified` field + pre-task check | ~15   | Low — additive, backward-compatible with old queues        |
| `aet-pipeline-implement` | Add `merged` stage + post-ship verification | ~20   | Low — new stage, doesn't affect existing stages            |

**Total:** ~60 lines across 3 skills. No breaking changes.

---

## 7. Alternative Approaches Considered

### Option A: Git Hook (rejected)

Add a `post-checkout` or `post-merge` hook that warns on `git reset --hard`.

- **Why rejected:** Hooks are project-local, invisible to agents, and can be bypassed. The toolkit should enforce behavior at the skill level.

### Option B: Wrapper Script (rejected)

Create a `git-safe-delete` alias.

- **Why rejected:** Aliases are user-local. AET is designed to be agent-driven, not alias-dependent.

### Option C: Enhanced `aet-evolve` (rejected)

Add "check for dangling commits" to the retro process.

- **Why rejected:** Retroactive detection is too late. The fix must be preventive, not detective.

---

## 8. Acceptance Criteria for Toolkit PR

- [ ] `aet-ship` halts with a clear warning if `git merge-base --is-ancestor HEAD origin/main` fails before branch deletion
- [ ] `aet-work` checks `merge_verified` on the previous task before starting the next
- [ ] `aet-pipeline-implement` supports a `merged` stage and updates `merge_verified` in the work queue
- [ ] All three skills reference the same verification command (`git merge-base --is-ancestor <ref> origin/main`)
- [ ] Backward-compatible: old work queues without `merge_verified` still work (treated as unverified, not broken)
- [ ] Documentation updated in each skill's `SKILL.md`

---

## 9. Files Changed in This Report

- `docs/retros/2026-05-16-lost-branch-retro.md` — Retro for this incident
- `docs/retros/2026-05-16-aet-toolkit-branch-safety-report.md` — This report
- `AGENTS.md` — Temporary project-level rule (to be removed once toolkit fix lands)
- `.agents/commands/branch-cleanup.md` — Temporary project-level command (to be removed once toolkit fix lands)
- `.agents/learnings.jsonl` — Learning entry

---

## 10. Next Steps

1. **Review this report** — discuss in AET project
2. **Create toolkit issues** — one per skill (`aet-ship`, `aet-work`, `aet-pipeline-implement`)
3. **Implement in priority order:** `aet-ship` first (highest leverage), then `aet-pipeline-implement`, then `aet-work`
4. **Remove project-level workarounds** — once toolkit fix is released, remove branch-cleanup rule from AGENTS.md and `.agents/commands/branch-cleanup.md`
5. **Propagate to all AET projects** — notify users to upgrade their toolkit skills

---

_Generated by aet-evolve retro + system-evolve cycle._

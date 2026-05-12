# Plan: aet-ship — Stacked Branch Detection

## Context

Retro: `docs/retros/2026-05-12-stacked-pr-base-not-updated.md`

S2-T2 was stacked on S2-T1. After S2-T1's PR merged to main, S2-T2's PR still targeted `s2-t1-runner-abort`. No warning surfaced. S2-T2 landed in the wrong branch and required a manual recovery merge.

Fix layer: `~/.claude/skills/aet-ship/SKILL.md` — add a **Stacked branch detection** step to the `ship` procedure, between step 1 (Sync with main) and step 2 (Run test suite).

## Architecture Decision

**No auto-rebase. No auto-base-update.** Both are irreversible and can silently misresolve conflicts. The fix is warning-only: surface the stacked relationship at PR creation time so the human acts at exactly the right moment (when reviewing the PR).

## Tasks

1. **Edit `~/.claude/skills/aet-ship/SKILL.md`** — insert new step `1a` (Stacked branch detection) between current step 1 and step 2 — **S**

   The new step reads:

   ```
   1a. **Stacked branch detection** — Run `git merge-base HEAD main` and compare to `git rev-parse main`.
       If they differ, the current branch was not branched directly from main's current tip — treat it as stacked.
       - Identify the parent branch: scan `git log --oneline --decorate main..HEAD` for the nearest named ancestor (the last commit decorated with a non-HEAD, non-remote ref).
       - Still create the PR against the parent branch (this is correct at creation time).
       - Prepend a `⚠️ STACKED PR` section to the PR body:
         > Base is `[parent-branch]`. After `[parent-branch]` is merged to main, run:
         > `git rebase main && git push --force-with-lease && gh pr edit --base main`
         > before merging this PR.
       - Print a terminal stop-note after PR creation:
         > ⚠️  STACKED PR: this PR targets [parent-branch], not main.
         > After [parent-branch] merges, you must rebase and update the base before merging this PR.
   ```

2. **Add a worked example to `~/.claude/skills/aet-ship/examples/`** — create `stacked-branch-example.md` showing the exact detection commands and the warning output — **S**

3. **Add a learning entry to `.agents/learnings.jsonl`** — record the root cause and fix pattern so future cycles don't repeat it — **XS**

## Dependencies

None — all three tasks are independent. Run 1 → 2 → 3 in order for clarity.

## Validation Steps

- [ ] `~/.claude/skills/aet-ship/SKILL.md` contains step `1a` between steps 1 and 2
- [ ] Step 1a describes detection via `git merge-base`, PR body injection, and terminal stop-note
- [ ] No mention of auto-rebase or auto-base-update in the new step
- [ ] Example file exists and shows realistic detection output
- [ ] Learnings entry added

## Rollback Plan

Revert the SKILL.md edit. The skill file is plain markdown — no dependencies, no side effects.

---

_Stage: synced_
_Next step: run `aet-ship`_

---
date: 2026-05-12
ticket: S2-T1 / S2-T2
stage: post-ship
---

# Retro: Stacked PR base not updated after parent merged

## What happened

Two tickets were implemented and shipped in sequence:

1. **S2-T1** (`s2-t1-runner-abort`) — added `abort()` / `getStatus()` to `IExecutionRunner`. `aet-ship` created PR #2 targeting `main`. ✓
2. **S2-T2** (`s2-t2-opencode-sdk-fix`) — fixed OpenCode SDK abort call shape and `noReply` guard. S2-T2 needed S2-T1's new interface to compile, so `aet-implement` correctly branched `s2-t2-opencode-sdk-fix` off `s2-t1-runner-abort` (stacked branch). `aet-ship` ran and called `gh pr create` **without `--base`**, so GitHub inferred the base as `s2-t1-runner-abort`. PR #3 was created targeting `s2-t1-runner-abort`. ✓ correct at creation time.

PR #2 was then merged into `main`. At that point, PR #3's base (`s2-t1-runner-abort`) was already in `main`, but **no one updated PR #3's base to `main`**. PR #3 was merged as-is, landing S2-T2 in `s2-t1-runner-abort` — not in `main`. Required a manual merge to recover.

## Root cause

`aet-ship` has no awareness of stacked branches. It calls `gh pr create` without `--base`, trusting GitHub's inference. When a branch is stacked, that inference points to the parent feature branch, not `main`. After the parent merges, the downstream PR's base becomes stale — but there is no warning, no flag, and no step in the workflow that prompts the human to update it.

## Why stacking was correct

Branching S2-T2 from `s2-t1-runner-abort` was the right call. S2-T1 added the `IExecutionRunner.abort()` interface that S2-T2 consumed. Branching from `main` instead would have caused compile errors and a messy conflict when trying to merge. The stacking was intentional and necessary.

## What went wrong

The workflow had no mechanism to surface the stacked relationship to the human at merge time. Once PR #2 landed, the engineer merging PR #3 had no visible signal that the base needed updating.

## Solution

**Creation-side warning only** — no automated rebase or base update (those are irreversible and risk silent conflict misresolution).

When `aet-ship` detects a stacked branch (current branch did not diverge directly from `main`), it should:

1. Still create the PR against the parent branch — that is correct.
2. Add a prominent `⚠️ STACKED PR` section in the PR body:
   > Base is `[parent-branch]`. After `[parent-branch]` is merged to main, rebase this branch onto main and run `gh pr edit --base main` before merging this PR.
3. Print a terminal stop-note so the user is aware before the session ends.

No auto-rebase. No auto-base-update. The human sees the warning at exactly the right moment (when reviewing the PR) and acts.

## Layer to fix

`~/.claude/skills/aet-ship/SKILL.md` — add a **Stacked branch detection** step to the `ship` procedure, between "Sync with main" and "Run test suite".

## Not yet applied

This retro documents the problem and proposed fix. The skill has **not** been updated. A human should review this retro and apply the change to `aet-ship` when ready.

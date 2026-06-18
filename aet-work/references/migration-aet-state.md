# Migrating to aet-state

## When to Read This

You are upgrading an existing project that already has `.agents/work-queue.json` to use the centralized `aet-state` helper for state transitions and transition validation.

## What Changes

Before `aet-state`, the work queue stored status directly in JSON and skills mutated it by hand. After `aet-state`, the queue records state forward through validated transitions, and `aet-state audit` can reconcile stored state against git ground truth on demand.

## One-Time Repair

Run this on any existing queue to detect stale or invented statuses without mutating the queue:

```bash
python3 ~/.claude/skills/aet-work/bin/aet-state audit .agents/work-queue.json
```

This prints stored and derived statuses for every task. If a task is stored as `awaiting_merge` or `merged` but git says otherwise, inspect manually and use `aet-state transition` or `aet-work mark-terminal` to repair.

To force a full repair:

```bash
# 1. Audit stored state against git ground truth
python3 ~/.claude/skills/aet-work/bin/aet-state audit .agents/work-queue.json

# 2. Re-init the queue (preserves completed tasks, normalizes new ones)
aet-work init-queue

# 3. Check for remaining discrepancies
aet-work status
```

## Common Stale States

| Stored state     | Likely derived status | Cause                                  |
| ---------------- | --------------------- | -------------------------------------- |
| `merged`         | `in-progress`         | Branch not yet on `origin/main`        |
| `awaiting_merge` | `in-progress`         | Pipeline finished but PR not merged    |
| `merge_verified` | `merged`              | Legacy alias; normalized automatically |
| `in_progress`    | `planned`             | Worktree removed, branch deleted       |

## Ongoing Maintenance

- Run `aet-work audit` when you suspect stored state has drifted from git reality
- Never edit `.agents/work-queue.json` by hand; use `aet-state transition` or `aet-work mark-terminal`
- If a task was abandoned with a `failure_reason`, clear the reason before transitioning it back to active

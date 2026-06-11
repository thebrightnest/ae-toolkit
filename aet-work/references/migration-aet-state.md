# Migrating to aet-state

## When to Read This

You are upgrading an existing project that already has `.agents/work-queue.json` to use the centralized `aet-state` helper for status derivation and transition validation.

## What Changes

Before `aet-state`, the work queue stored status directly in JSON and skills mutated it by hand. After `aet-state`, status is **derived from ground truth** (git, filesystem) and transitions are **validated for legality** before applying.

## One-Time Repair

Run this on any existing queue to detect and repair stale or invented statuses:

```bash
python3 ~/.claude/skills/aet-work/bin/aet-state derive .agents/work-queue.json
```

This prints derived statuses for every task. If a task is stored as `done` or `merged` but git says otherwise, `aet-work status` will flag the mismatch after you run `init-queue` or `sync`.

To force a full repair:

```bash
# 1. Derive ground truth
python3 ~/.claude/skills/aet-work/bin/aet-state derive .agents/work-queue.json

# 2. Re-init the queue (preserves completed tasks, re-derives new ones)
aet-work init-queue

# 3. Check for remaining mismatches
aet-work status
```

## Common Stale Statuses

| Stored status    | Likely derived status | Cause                                  |
| ---------------- | --------------------- | -------------------------------------- |
| `merged`         | `in-progress`         | Branch not yet on `origin/main`        |
| `done`           | `in-progress`         | Pipeline finished but PR not merged    |
| `merge_verified` | `merged`              | Legacy alias; normalized automatically |
| `in-progress`    | `planned`             | Worktree removed, branch deleted       |

## Ongoing Maintenance

- Run `aet-work derive` (or let `status`/`next` run it automatically) before trusting queue output
- Never edit `.agents/work-queue.json` by hand; use `aet-state transition` or `aet-work mark-terminal`
- If a task was abandoned with a `failure_reason`, clear the reason before transitioning it back to active

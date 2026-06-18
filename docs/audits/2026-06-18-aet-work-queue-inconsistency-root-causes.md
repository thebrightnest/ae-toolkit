# Audit: aet-work Queue Inconsistency Root Causes

**Date:** 2026-06-18
**Auditor:** agent session
**Scope:** `.agents/work-queue.json`, `.agents/work-archive.json`, `docs/plans/*.md`, `aet-work/bin/aet-state` derive logic

## Executive Summary

Running `aet-work derive` on 2026-06-18 surfaced a large number of tasks that appeared to be actionable (`unblocked`) despite having been implemented weeks or months ago. The commands are not broken; they exposed pre-existing data-hygiene problems in the work queue. This report documents the root causes, quantifies the inconsistencies, and recommends fixes.

## Key Findings

| Metric                                                                    | Value   |
| ------------------------------------------------------------------------- | ------- |
| Active queue tasks                                                        | 86      |
| Active tasks with `planned` status                                        | 81      |
| Active tasks with `merged` status (not archived)                          | 5       |
| Archived tasks                                                            | 88      |
| `planned` tasks whose plan footer already says implemented/shipped/merged | 21      |
| `planned` tasks blocked by already-implemented dependencies               | several |

## Root Cause 1: Terminal Tasks Never Archived

The active queue still contains tasks whose status is terminal (`merged`, `done`, `abandoned`). The `aet-state archive` command exists and correctly moves terminal tasks to `.agents/work-archive.json` when they have no active dependents, but it was not run consistently.

**Evidence:**

- 5 tasks are `merged` and still active.
- 88 tasks are already in the archive, proving the archive path works but was not applied exhaustively.

**Impact:**

- `aet-work status` reports terminal tasks as active.
- `aet-work next` can pick a `merged` task if its stored status is ever reset or if derive disagrees with stored status.

## Root Cause 2: Completed Work Lacks `merge_commit` or Branch

`aet-state derive` trusts only two ground-truth signals:

1. A local branch exists → `in-progress`.
2. The branch or the task's `merge_commit` is an ancestor of `origin/main` → `merged`.

When work is squash-merged and the branch is deleted, the original branch commits are **not** ancestors of `origin/main`. Only the squash commit is. If `aet-ship` or a manual process does not record that squash commit in the task's `merge_commit` field, derive can never verify the merge.

**Evidence:**

- Many PRs in this repo are squash-merged.
- The 5 active `merged` tasks were set to `merged` by recent manual bookkeeping, but their `merge_commit` fields were set to unrelated recent commits because the true squash commits were not known or recorded.

**Impact:**

- Tasks that are genuinely in `main` are not recognized as merged by derive.
- They fall back to `unblocked` (plan exists, no branch), making old work look like new work.

## Root Cause 3: `derive` Ignores Plan Footers

`aet-state derive` does not read plan markdown footers. It has no knowledge of `*Stage: implemented*`, `*Stage: shipped*`, or `*Stage: merged*`.

**Evidence:**

- 21 active `planned` tasks have plan footers that say implemented/shipped/merged.
- Examples include `aet-work-run-unification-plan`, `parallel-01-orchestrator-core`, `waf-01-aet-work-queue-state`.

**Impact:**

- A task can be fully implemented and documented as such in its plan, but derive reports it as `unblocked` because the branch is gone and `merge_commit` is empty.
- This is the primary mechanism by which `aet-work derive` "brought back" completed tasks.

## Root Cause 4: Plan Footers and Queue Status Are Separate Truths

There are two parallel state representations:

1. **Queue JSON** (`status`, `merge_commit`, `worktree`, `branch`).
2. **Plan footer** (`*Stage: ...*`).

They are updated by different commands and nothing reconciles them automatically. A task can say `implemented` in its plan footer while the queue still says `planned`.

**Evidence:**

- `aet-state sync-footers` exists to update both atomically, but it is opt-in and was not run across the backlog.
- The design-system tickets (`01-scaffold-skill-structure` through `04-port-phase-5-preview`) had plan footers added recently, but their queue entries were only partially updated.

## Root Cause 5: Direct-to-Main Work Never Recorded

Some tasks were implemented by committing directly to `main` without a branch or PR. Because derive requires a branch or `merge_commit`, these tasks remain `planned` forever unless manually marked.

**Evidence:**

- Several early skills and docs were bootstrapped on `main`.
- `aet-design-system-creation` skill content exists in `main` (commit `f947c27` from 2026-05-04) but the corresponding queue tasks were still `planned`.

**Impact:**

- Old bootstrap work looks permanently unstarted.
- Running `aet-work run` would try to re-implement already-existing skills.

## Root Cause 6: Blocker Chains Use Stored Status, Not Derived Status, in Some Paths

`derive` computes blocker status recursively, but other commands (e.g., older versions of `next`) used stored `status` directly. When stored status is stale, dependent tasks are blocked or unblocked incorrectly.

**Evidence:**

- `02-port-phases-0-2` was `planned` but its dependents `03-port-phases-3-4`, `04-port-phase-5-preview`, and `05-integration-polish` were derived as `blocked` because of the stale blocker status.
- After marking `02-port-phases-0-2` as `planned` again, the dependents returned to `blocked`.

## Recommended Fixes

### Immediate (data cleanup)

- **Run `aet-state archive`** to move all terminal tasks out of the active queue.
- **Reconcile plan footers with queue status:**
  - For tasks with `*Stage: implemented*` but no merge commit, find the commit on `origin/main` that introduced the work and set `merge_commit`.
  - For direct-to-main bootstrap work, mark as `done` or `merged` with the appropriate commit.
- **Verify the 5 active `merged` tasks** have correct `merge_commit` values pointing to real squash commits.

### Short-term (tooling improvements)

- **Teach `aet-state derive` to read plan footers.** Treat `*Stage: implemented*`/`shipped`/`merged` as an additional ground-truth signal. When no branch exists and no `merge_commit` is set, a task whose plan footer says implemented should derive to at least `done` (with a warning if merge verification is missing), not `unblocked`.
- **Add an `aet-state audit` command** that reports mismatches such as:
  - `planned` but footer says implemented
  - `merged` but not an ancestor of `origin/main`
  - terminal status still in active queue
  - plan file missing for an active task

### Long-term (process)

- **Make `aet-ship` always record `merge_commit`** for squash merges, even when merge verification is performed via `gh`.
- **Run `aet-state archive` automatically** after `aet-ship` completes or as part of `aet-work run` cleanup.
- **Adopt a single source of truth** for task state: prefer derived status for scheduling, but require `merge_commit` or plan-footer evidence before archiving.

## Appendix: Commands Used

```bash
# Queue status summary
python3 -c "import json; q=json.load(open('.agents/work-queue.json')); t=q.get('tasks',[]); print({s: sum(1 for x in t if x.get('status')==s) for s in set(x.get('status','unknown') for x in t)})"

# Archived task count
python3 -c "import json; a=json.load(open('.agents/work-archive.json')); print(len(a.get('tasks',[])))"

# Planned tasks with implemented footers
python3 -c "
import json
q=json.load(open('.agents/work-queue.json'))
for t in q.get('tasks',[]):
    if t.get('status')=='planned':
        try:
            if 'Stage: implemented' in open(t['plan_file']).read():
                print(t['id'])
        except FileNotFoundError:
            pass
"

# Derive current statuses
python3 ~/.claude/skills/aet-work/bin/aet-state derive .agents/work-queue.json
```

## Related Documents

- `docs/retros/2026-06-18-orchestrator-hang-no-recovery.md`
- `docs/audits/2026-06-17-aet-work-queue-state-review.md`
- `.agents/learnings.jsonl` (entries with triggers `orchestrator`, `hang`, `timeout`, `watchdog`, `subprocess`, `batch`)

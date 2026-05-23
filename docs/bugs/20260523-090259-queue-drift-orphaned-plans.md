## Bug Report: Queue Drift from Source Plans — Orphaned Follow-Up Plans Creating False Completion Signals

## Metadata

- **Reported:** 2026-05-23T09:02:59+00:00
- **Severity:** high
- **Status:** resolved

## Symptoms

The work queue (`.agents/work-queue.json`) reported 24 of 25 tracked tasks as `done`/`merge_verified`, with only 1 task `unblocked`. This gave the appearance of a project nearing completion. However, 7 plan files existed in `docs/plans/` with no corresponding entries in the queue:

- `docs/plans/aet-work-run-unification-plan.md`
- `docs/plans/aet-work-runtime-self-detection-plan.md`
- `docs/plans/aet-work-yaml-fix-plan.md`
- `docs/plans/ccs-01-review-css-lens.md`
- `docs/plans/ccs-02-template-framework-doc.md`
- `docs/plans/planning-implementation-lockout-plan.md`
- `docs/plans/retro-stacked-pr-aet-ship-plan.md`

These orphaned plans documented recovery work, cleanup tasks, and follow-ups from previously "completed" work. Because they were untracked, no agent ever picked them up, creating invisible technical debt and a false "all clear" signal.

## Reproduction Steps

1. Start with a project using `aet-work` and an initialized queue
2. Add new plan files to `docs/plans/` (e.g., follow-up recovery plans after merging a feature)
3. Do **not** re-run `init-queue`
4. Run `aet-work status` — it reports all tracked tasks complete
5. Observe that the new plans are never surfaced to any agent

**Confirmed in this repo:** 25 queue entries vs 32 plan files on disk = 7 orphaned plans.

## Root Cause

The `aet-work` skill treated the queue as a write-once bootstrap artifact rather than a living document synchronized with its source of truth (`docs/plans/*.md`).

- **Static queue, dynamic plans:** `status`, `next`, and `run` all read `.agents/work-queue.json` without ever comparing it against the current contents of `docs/plans/`. New plans could be added, renamed, or deleted without the queue noticing.
- **No validation gate:** No command existed to detect plan-to-queue skew. The existing `drift-check` only verified git ancestry for done tasks — it did not check for missing plan files.
- **Overwriting init-queue:** The `init-queue` procedure instructed the agent to "Write `.agents/work-queue.json`" with no merge semantics, implicitly encouraging full overwrites that would destroy existing task statuses.
- **Missing timestamp:** The queue file carried no `queue_updated_at` field, making it impossible to detect stale queues by comparing against plan file modification times.

## Fix Summary

Updated `aet-work/SKILL.md` with plan-drift detection and merge-safe queue initialization.

- **Files modified:** `aet-work/SKILL.md`
- **Key changes:**
  1. Added `plan-drift` command that compares `docs/plans/*.md` against queue entries and reports orphaned plans + stale queue warnings
  2. Updated `init-queue` to merge new plans into an existing queue instead of overwriting, preserving all statuses and metadata
  3. Added `queue_updated_at` timestamp to the queue file
  4. Updated `status`, `next`, and `run` to run the `plan-drift` check before proceeding, refusing to report "all clear" or start the AFK loop when drift is detected
- **Side effects:** `init-queue` is now safe to re-run at any time without losing work history

## Regression Test

After the fix, running the `plan-drift` logic against the current repo state correctly surfaces all 7 orphaned plans and the stale-queue warning:

```
⚠️ Plan drift detected: 7 plan file(s) not in queue
   - docs/plans/aet-work-run-unification-plan.md
   - docs/plans/aet-work-runtime-self-detection-plan.md
   - docs/plans/aet-work-yaml-fix-plan.md
   - docs/plans/ccs-01-review-css-lens.md
   - docs/plans/ccs-02-template-framework-doc.md
   - docs/plans/planning-implementation-lockout-plan.md
   - docs/plans/retro-stacked-pr-aet-ship-plan.md

⚠️ Queue is stale (plans modified after last init-queue).
```

## Validation

- [x] Reproduction steps now surface the bug via `plan-drift` instead of hiding it
- [x] `make validate` passes (lint, format-check, skill-structure validator)
- [x] `aet-work/SKILL.md` remains under 400 lines (191 lines)
- [x] No regressions in other skill commands (`drift-check`, `cleanup`, orchestrator behavior unchanged)

## Lessons Learned

- **Pattern:** Write-once config/artifact drift — a static snapshot falling out of sync with its dynamic source of truth.
- **Prevention:** Every artifact that claims to represent a living directory (queue, index, manifest) needs a built-in drift-detection command and every read-path should run it.
- **Reference:** Updated `aet-work/SKILL.md` with `plan-drift` command and merge semantics for `init-queue`.

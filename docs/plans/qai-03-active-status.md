# Plan: Active-Only Status View

## Context

Parent PRD: `docs/prds/aet-work-queue-archival-incremental-sync-prd.md`
Depends on: `qai-01-archive-cleanup` (archive file must exist to count archived tasks)

This plan updates `aet-work status` to display only active tasks by default, with a note about how many tasks are archived.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **Update `aet-work/SKILL.md` status procedure** — M

   - Step 4: Change counts to report only `unblocked`, `blocked`, `in-progress`, `failed`, `done`
   - Remove `merged`, `merge_verified` from the count report
   - Step 5 (Derived status column): Show derived vs. stored only for active tasks
   - Step 7: "Next 3 unblocked tasks" remains unchanged (now naturally operates on smaller active set)
   - New step after counts: Print `N tasks archived. Run aet-work cleanup to archive terminal tasks.`
   - Remove step 6 (Legacy status nudge) — `merge_verified` is handled by archive/cleanup now

2. **Update `aet-work/SKILL.md` plan-drift procedure** — S

   - No functional change, but add note that plan-drift checks against the active queue only
   - Archived tasks are not checked for drift (their plan files may still exist, but they are no longer tracked)

3. **Merge branch to main and verify integration** — S

## Dependencies

- Blocked by `qai-01-archive-cleanup` — archive file must exist so the status command can reference it for the count note.

## Validation Steps

- [ ] `make validate` passes
- [ ] `aet-work status` (as executed by the agent) reports active task counts (`unblocked`, `blocked`, `in-progress`, `failed`, `done`)
- [ ] `aet-work status` prints the archive count note when tasks have been archived
- [ ] No references to `merge_verified` remain in the `status` procedure

## Rollback Plan

1. Revert `aet-work/SKILL.md` changes.
2. Re-run `aet-work init-queue` if needed.

---

_Stage: plan-approved_
_Next step: run `aet-work`_

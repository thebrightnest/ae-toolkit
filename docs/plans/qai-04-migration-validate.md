# Plan: One-Time Migration and Full Validation

## Context

Parent PRD: `docs/prds/aet-work-queue-archival-incremental-sync-prd.md`
Depends on: `qai-01-archive-cleanup`, `qai-03-active-status`

This plan migrates the existing 65 merged/done tasks from the active queue to the archive, validates the new behavior end-to-end, and updates any remaining documentation references.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **Run one-time migration** — S

   - Execute `python3 aet-work/bin/aet-state archive .agents/work-queue.json .agents/work-archive.json`
   - Verify: `.agents/work-archive.json` contains 65+ terminal tasks
   - Verify: `.agents/work-queue.json` contains only active tasks (unblocked, blocked, in-progress, failed)
   - Commit both files with message: `chore(queue): archive terminal tasks after qai rollout`

2. **Run performance validation** — S

   - `time python3 aet-work/bin/aet-state derive .agents/work-queue.json` — must be < 1 second on the active queue
   - `time aet-work sync` (simulated) — must be < 2 seconds
   - Document baseline times in a comment or ADR note

3. **Update `docs/CONVENTIONS.md` if needed** — S

   - Add note: terminal tasks are archived, not kept in active queue
   - Update any queue examples to reflect the active-only convention

4. **Update `CHANGELOG.md`** — S

   - Document: archive file, active-only status, cleanup atomicity

5. **Run full `make validate`** — S

   - Lint, format-check, skill-structure validator all pass
   - Ensure no broken internal links after SKILL.md changes

6. **Merge branch to main and verify integration** — S

## Dependencies

- Blocked by `qai-01-archive-cleanup` (archive command must exist)
- Blocked by `qai-03-active-status` (status must reflect active-only view)

## Validation Steps

- [ ] `make validate` passes
- [ ] `.agents/work-archive.json` exists and contains only terminal tasks
- [ ] `.agents/work-queue.json` contains only active tasks
- [ ] `aet-work status` shows only active tasks with archive count note
- [ ] `aet-work cleanup` removes worktrees only after successful archive

## Rollback Plan

1. Restore `.agents/work-queue.json` and `.agents/work-archive.json` from the migration commit.
2. If needed, manually move archived tasks back into the active queue by editing JSON.
3. Re-run `aet-work init-queue` as last resort.

---

_Stage: plan-approved_
_Next step: run `aet-work`_

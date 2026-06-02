# Plan: Parallel Orchestrator Core

## Context

PRD: `docs/prds/aet-work-parallel-execution-prd.md`

Upgrades the generated bash orchestrator from sequential to parallel execution. This is the mechanical core of the feature: job control, concurrency capping, drain-on-failure, and race-free queue updates.

## Tasks

1. **Rewrite orchestrator template for parallel job control** — M ✓

   - Replace the single `while true` sequential loop with a main loop that tracks running jobs via bash job control
   - Maintain a `SLOTS` counter (current running jobs) and `MAX_JOBS` cap
   - Spawn unblocked tasks as background jobs until cap reached or no tasks remain
   - Use `wait -n` (or compatible polling) to detect job completion
   - On success: mark `done`, promote dependents, decrement slot, immediately try to spawn next
   - On failure: set `STOP_SPAWN=1`, mark `failed`, drain remaining jobs, exit 1
   - On startup: scan `in-progress` tasks, warn if worktree exists but no PID detectable, mark `failed` to unblock resume

2. **Add concurrency cap detection** — S ✓

   - Read `AET_WORK_JOBS` env var
   - Fixed fallback of `4`
   - Hard ceiling at `8` to prevent fork bombs
   - Echo detected cap at orchestrator startup

3. **Add end-of-run summary** — S ✓

   - Print counts: succeeded, failed, skipped (already done), wall-clock elapsed time
   - Print next-step hint: `aet-work cleanup` or `aet-work status`

4. **Merge branch to main and verify integration** — S ⏳ (deferred to aet-ship)

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Dependencies

- None — this is the first task in the parallel upgrade
- Blocks `parallel-02-skill-docs` (docs should reference the implemented behavior)

## Validation Steps

- [ ] Generated script passes `shellcheck` (if available) or manual bash syntax check
- [ ] `make validate` passes
- [ ] `make package` regenerates `.skill` files
- [ ] Manual verification: create a mock queue with 3 independent no-op tasks, run orchestrator, verify they execute concurrently
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

- Revert `aet-work/references/orchestrator-template.sh` to previous version
- Regenerate `scripts/.aet-work-orchestrator.sh` from the old template
- The old sequential behavior is still valid (cap = 1 is a supported configuration)

---

\_Stage: merged
\_Next step: none — pipeline complete

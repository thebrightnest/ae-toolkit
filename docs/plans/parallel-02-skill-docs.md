# Plan: Parallel Skill Documentation

## Context

PRD: `docs/prds/aet-work-parallel-execution-prd.md`
Parent task: `parallel-01-orchestrator-core`

Updates `aet-work` skill documentation to reflect the new parallel execution behavior, concurrency controls, and failure semantics.

## Tasks

1. **Update `aet-work/SKILL.md` `run` command** — M

   - Update the procedure to mention parallel execution (still reads template, still spawns background, but now multiple concurrent)
   - Update the Context Isolation mechanism diagram to show multiple simultaneous processes
   - Update the Key Principles section:
     - Remove "v3: parallel execution — future iteration" line
     - Replace "Fail fast, stop clean" with "Drain on failure — running tasks finish, new spawns halt"
   - Add mention of `AET_WORK_JOBS` env var and default cap behavior
   - Keep SKILL.md under 400 lines; move deep detail to `references/`

2. **Update `aet-work/references/context-isolation.md`** — S

   - Document why parallel execution is safe (worktree + process isolation)
   - Document the drain-on-failure behavior and why it preserves in-progress work
   - Document the queue-update invariant (only main loop writes)

3. **Add `aet-work/references/parallel-execution.md` (optional)** — S

   - Deep dive on bash job control approach
   - Concurrency cap algorithm
   - Resume behavior under parallelism
   - Only create if content exceeds what fits in context-isolation.md

4. **Merge branch to main and verify integration** — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Dependencies

- Blocked by `parallel-01-orchestrator-core` (docs must describe implemented behavior)

## Validation Steps

- [ ] `make lint` passes on all modified markdown files
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] `make package` regenerates `.skill` files
- [ ] SKILL.md line count ≤ 400
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

- Revert `aet-work/SKILL.md` and `aet-work/references/` files to previous versions
- Re-package skills with `make package`

---

\_Stage: merged
\_Next step: none — pipeline complete

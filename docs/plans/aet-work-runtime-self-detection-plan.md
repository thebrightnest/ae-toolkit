---
id: aet-work-runtime-self-detection-plan
blocked_by: []
size: M
---

# Plan: Fix aet-work `run` Runtime Detection to Use Current Agent

## Context

- PRD: `docs/prds/aet-work-runtime-self-detection-prd.md`
- Related prior work: `docs/prds/aet-work-hybrid-orchestrator-prd.md` (introduced runtime detection), `docs/prds/aet-work-run-unification-prd.md` (unified `run` command)
- The bug: `aet-work run` checks installed binaries in PATH with a hard-coded priority list (`kimi` first, then `claude`). When multiple agents are installed, the generated orchestrator script may invoke the wrong CLI.
- The fix: replace all external detection with a single self-reporting step where the currently running agent states its own CLI command and flags.

## Tasks

1. **Rewrite runtime detection in `aet-work/SKILL.md`** — M

   - Replace the "Runtime detection" procedure under `run` command with self-identification logic
   - Detection asks the currently running agent to identify its own CLI command and flags; no env vars, no PATH scanning, no priority list, no override knob, no hard-coded table
   - Update the CLI substitution variable table if needed
   - Keep `make validate` under 400 lines (SKILL.md is currently 167 lines; plenty of room)

2. **Update `aet-work/references/context-isolation.md`** — S

   - Update the "Runtime Capability Reference" section to mention that `run` detects the current runtime, not the first installed binary
   - No other structural changes

3. **Validate and package** — S
   - Run `make validate`
   - Run `make package`
   - Confirm `.skill` files are regenerated

## Dependencies

- Task 1 blocks Task 2 (docs depend on the skill wording being final)
- Task 2 blocks Task 3 (validation runs on final state)

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes (includes skill-structure validator)
- [ ] `make package` regenerates `.skill` files without errors
- [ ] Manual check: read the generated `aet-work/.skill` file (or unzip it) and confirm the `run` section describes self-detection
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

If the new detection logic causes issues:

1. Revert the "Runtime detection" section in `aet-work/SKILL.md` to the previous priority-list version
2. Revert `aet-work/references/context-isolation.md` changes
3. Run `make validate && make package`

---

_Stage: merged_
_Next step: none — pipeline complete_

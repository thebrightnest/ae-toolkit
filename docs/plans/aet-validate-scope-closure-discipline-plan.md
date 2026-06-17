# Plan: Add Closure Checks to Planning and Validation Skills

## Context

- PRD: `docs/prds/aet-work-queue-state-refactor-prd.md` surfaced the symptom, but the root cause is general.
- Problem: `aet-validate-scope` can mark a PRD as `scope-validated` even when no `docs/plans/*.md` files have been created or synced to `.agents/work-queue.json`. `aet-pipeline-plan` also declares completion after `aet-work sync` without verifying the result.
- Impact: Planning sessions end with approved documents but no actionable queued tasks, breaking the handoff to `aet-work` / `aet-pipeline-implement`.

## Tasks

1. **Add a closure check to `aet-validate-scope/SKILL.md`** — M

   - In the `validate` command procedure, after conflicts are resolved and before updating footers, add a **Closure Check** step:
     1. List all `docs/plans/*.md` files that reference the PRD (e.g., contain the PRD path in their Context section or frontmatter).
     2. If zero plan files exist, stop and print:
        > "Scope validation cannot complete: no plan files found for this PRD. Run `aet-plan` to break the PRD into `docs/plans/*.md` files, then re-run `aet-validate-scope`."
     3. Load `.agents/work-queue.json` and verify every plan file from step 1 is present in the queue.
     4. If any plan file is missing from the queue, stop and print:
        > "Scope validation cannot complete: plan files exist but are not synced to the work queue. Run `aet-work sync`, then re-run `aet-validate-scope`."
   - Update the Completion Protocol to state that footers are updated only after the closure check passes.

2. **Verify sync result in `aet-pipeline-plan/SKILL.md`** — S

   - In Step 3 (`aet-work sync`), after running sync, run `aet-work status` and confirm:
     - No plan drift.
     - At least one task from the new plans appears in the queue summary.
   - If drift or missing tasks are reported, stop and resolve them before declaring the pipeline complete.
   - Update the Completion Protocol artifact list to include a verified queue sync.

3. **Reinforce queue handoff in `aet-plan/SKILL.md`** — S

   - In `create-stories`, after writing plan files, add an explicit bullet:
     - **Run `aet-work sync`** to add the new plans to `.agents/work-queue.json` before marking the command complete.
   - In the Completion Protocol, add a check that the queue contains the new plan files.

4. **Validate and package** — S
   - Run `make lint`, `make format-check`, `make validate`, and `make package`.

## Dependencies

- None.

## Validation Steps

- [ ] `aet-validate-scope/SKILL.md` contains a Closure Check that refuses to mark `scope-validated` when plan files are missing or unsynced.
- [ ] `aet-pipeline-plan/SKILL.md` Step 3 verifies sync via `aet-work status` before completion.
- [ ] `aet-plan/SKILL.md` explicitly instructs running `aet-work sync` after creating plan files.
- [ ] `make lint` passes.
- [ ] `make format-check` passes.
- [ ] `make validate` passes.
- [ ] `make package` regenerates `.skill` files.

## Rollback Plan

1. Revert the three `SKILL.md` files to their pre-edit state.
2. Run `make validate && make package`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_

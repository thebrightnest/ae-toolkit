# Plan: Skill Atomicity Updates

## Context

PRD: `docs/prds/work-queue-atomicity-boundary-prd.md`

Update three skill files to codify the directory separation between atomic task plans and non-atomic planning artifacts (roadmaps, audits, meta-plans).

## Tasks

1. ✓ **Update `aet-work/SKILL.md`** — Add atomicity filtering to `init-queue` and `sync` — S

   - In `init-queue` step 1: Clarify that `docs/plans/*.md` is for atomic plans only; non-atomic docs belong in `docs/roadmaps/` or `docs/audits/`
   - In `sync` step 3: Add a lightweight sanity check — if a scanned plan references other plan files or contains multiple "Phase" sections, emit a warning and skip it
   - In `plan-drift` step 2: Note that drift detection only considers `docs/plans/*.md`

2. ✓ **Update `aet-plan/SKILL.md`** — Add directory constraints — S

   - In `create-stories` step 2: Specify that atomic task plans MUST be saved to `docs/plans/{ticket-id}-plan.md`; roadmaps, audits, and meta-plans MUST be saved to `docs/roadmaps/` or `docs/audits/`
   - In `plan` step 3: Reiterate that the output path must be `docs/plans/` for atomic plans

3. ✓ **Update `aet-pipeline-plan/SKILL.md`** — Reference directory constraint — S

   - In Step 4 (`aet-work sync`): Add a note that `sync` only adds atomic plans from `docs/plans/` and ignores non-atomic documents stored elsewhere

4. ✓ **Update `AGENTS.md`** — Add `docs/roadmaps/` and `docs/audits/` to the workflow guardrails line that lists where planning artifacts belong — S

5. ✓ **Run `make validate`** — Verify lint, format, and skill structure pass — S

## Dependencies

- None — can start immediately

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] Skill structure validator passes for affected skills
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the three skill files to their pre-edit state via `git checkout -- aet-work/SKILL.md aet-plan/SKILL.md aet-pipeline-plan/SKILL.md`

---

_Stage: merged_
_Next step: none — pipeline complete_

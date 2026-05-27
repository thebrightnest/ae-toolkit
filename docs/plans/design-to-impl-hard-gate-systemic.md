# Plan: Systemic Design-to-Implementation Hard Gate

## Context

The agent interpreted "yes" to a planning question as carte blanche to implement 3 skill file changes immediately. AGENTS.md in the toolkit repo was updated with a hard gate, but AGENTS.md is project-local and does not travel with `.skill` files. `aet-prime` was considered as a delivery vehicle, but it is not auto-invoked on every session. We need a solution that ensures every AET-enabled project has this guardrail by default.

## Tasks

1. **Audit current delivery mechanisms** — map how guardrails currently reach user projects (aet-setup AGENTS.md template, skill instructions, etc.) — S
2. **Update `aet-setup` AGENTS.md template** — add the design-to-implementation hard gate to `aet-setup/examples/AGENTS.md.example` and update `aet-setup/SKILL.md` methodology to require it — M
3. **Add skill-level gates to implementation skills** — add explicit approval checkpoint steps to `aet-implement` and `aet-pipeline-implement` procedures so they gate before writing code regardless of project AGENTS.md — M
4. **Add `.agents/commands/approval-checkpoint.md` to aet-setup output** — ensure aet-setup generates this command file in new projects, making the gate actionable — S
5. **Validate and package all affected skills** — run `make validate`, `make package`, verify no regressions — S
6. **Merge branch to main and verify integration** — S

## Dependencies

- Task 1 (audit) blocks Task 2 (aet-setup template)
- Task 2 (aet-setup) and Task 3 (skill-level gates) can run in parallel
- Task 4 depends on Task 2
- Task 5 depends on Tasks 2, 3, 4
- Task 6 depends on Task 5

## Validation Steps

- [x] `make validate` passes
- [x] `make package` regenerates all `.skill` files
- [x] AET example AGENTS.md includes the hard gate
- [x] aet-implement and aet-pipeline-implement SKILL.md files include approval checkpoint steps
- [x] No skill exceeds 400 lines
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Divergence Summary

- Tasks 1–4 (audit, aet-setup template, skill-level gates, approval-checkpoint command) were already completed in earlier commits (`170cbc2`, `311b34a`) on main. This pipeline run addressed the remaining line-count violation in `aet-setup/SKILL.md` (412 → 370 lines) and regenerated `.skill` packages.
- Task 6 (merge to main) is deferred to `aet-ship` + `post-ship-verify` per pipeline protocol.

## Rollback Plan

Revert the modified `SKILL.md` files and the `AGENTS.md.example` template. Re-run `make package`.

---

_Stage: merged_
_Next step: none — pipeline complete_

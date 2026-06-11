# Plan: Unified Orchestrator with Session-Isolated Pipeline

## Context

- PRD: `docs/prds/unified-orchestrator-session-isolated-pipeline.md`
- Retro: `docs/retros/2026-06-10-orchestrator-uncommitted-changes.md`
- Replaces: `aet-pipeline-implement` skill + per-project `scripts/.aet-work-orchestrator.sh`

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **Create `aet-work/lib/` modules** — M

   - `cli_adapter.py`: `CLIAdapter` dataclass, Kimi + Claude adapters, explicit `--cli-bin` resolution
   - `pipeline.py`: `STAGES` list, session groups, isolation levels, conditional stage logic
   - `queue.py`: read/write queue JSON, promote dependents, mark status
   - `worktree.py`: create/remove worktrees, copy untracked plans, disk estimation
   - `verifier.py`: commit count check, stage advancement read from plan footer, retry logic

2. **Create `aet-work/bin/orchestrator`** — M

   - Argument parsing (`--queue-file`, `--plan-file`, `--cli-bin`, `--isolation`, `--max-jobs`)
   - Batch mode: parallel task spawning with slot pool, PID tracking, drain-on-failure
   - Single-plan mode: sequential stage advancement through session groups
   - Signal handlers (`SIGINT`, `SIGTERM`) for graceful shutdown
   - Prompt construction per stage group
   - Trust boundary enforcement (CLI allowlist, no global config mutation)

3. **Update `aet-work/SKILL.md` and remove legacy files** — S

   - Rewrite `run` command to invoke `bin/orchestrator` instead of generating a bash script
   - Add `run-one` alias (or document `--plan-file` usage)
   - Delete `aet-work/references/orchestrator-template.sh`
   - Delete `aet-pipeline-implement/` directory entirely
   - Update `aet-work/references/` README if it references the old template

4. **Update documentation** — S

   - `docs/PIPELINE.md`: orchestrator is the sole conductor, stage machine diagram
   - `docs/use-cases.md`: replace `aet-pipeline-implement` references with `aet-work run --plan-file`
   - `aet-setup/checklist.md` or template: remove `scripts/.aet-work-orchestrator.sh` from `.gitignore` recommendations

5. **Add unit tests** — M

   - `tests/test_cli_adapter.py`: adapter selection, flag generation, explicit bin resolution
   - `tests/test_pipeline.py`: stage transitions, conditional skips, isolation levels
   - `tests/test_verifier.py`: commit verification, stage advancement, retry behavior
   - `tests/test_queue.py`: status updates, dependent promotion

6. **Merge to main and validate** — S
   - Run `make validate`
   - Run test suite
   - Delete `scripts/.aet-work-orchestrator.sh` from this repo
   - Verify no `aet-pipeline-implement` references remain

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Dependencies

- Task 1 blocks Task 2 (lib modules used by orchestrator)
- Task 2 blocks Task 3 (orchestrator must exist before updating skill docs)
- Task 3 blocks Task 4 (docs reference new behavior)
- Tasks 1-4 block Task 5 (tests cover implemented code)
- Tasks 1-5 block Task 6 (merge)

## Validation Steps

- [ ] `make validate` passes (lint + format + skill structure)
- [ ] `python3 -m pytest tests/` passes
- [ ] `aet-work/bin/orchestrator --help` runs without error
- [ ] Integration test (manual): run `--plan-file` on a toy plan in a temp repo and verify stages advance
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

If the unified orchestrator fails in production:

1. Revert the commit that introduced it.
2. The old `aet-work/references/orchestrator-template.sh` and `aet-pipeline-implement/` are in git history and can be restored.
3. Projects with legacy `scripts/.aet-work-orchestrator.sh` can continue using it until they update.
4. No data migration is needed — queue JSON and plan.md footers remain compatible.

_Stage: qa-complete_
_Next step: run `aet-review`_

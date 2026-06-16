# Plan: aet-state and Telemetry Foundation

## Context

Implements Phase 0 of `docs/prds/aet-work-local-orchestrator-state-parallel-prd.md`.

Before building the unified orchestrator, we need a trustworthy state layer and execution telemetry. This plan delivers:

- A standalone `aet-state` helper that derives queue status from git + filesystem ground truth.
- An append-only `.agents/execution.log.jsonl` schema and supporting module.
- A basic `aet-work report` command.

The orchestrator (Phase 1) will be built on top of these primitives.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Tasks

1. **Define declarative queue schema and plan footer contract** — S

   - Reduce `work-queue.json` to DAG, `isolation_level`, `abandoned` flag + reason, and opaque metadata.
   - Define how `aet-state derive` maps ground-truth signals to canonical statuses.

2. **Implement `scripts/aet-state.py`** — M

   - `derive`: recompute every task status from branches, worktrees, plan footers, and git ancestry.
   - `transition --task-id <id> --to-stage <stage>`: atomic queue + plan footer update.
   - `reconcile --task-id <id> --to-stage <stage>`: manual override when queue/footer disagree.

3. **Implement telemetry module (`aet-work/lib/telemetry.py`)** — M

   - Append-only writer for `.agents/execution.log.jsonl`.
   - Per-stage and per-run summary record schemas.
   - Null-safe token/cost handling.

4. **Add `aet-work report` command** — S

   - Read `execution.log.jsonl` and print a text summary: runs, success/failure counts, wall-clock time, average isolation level.

5. **Update `aet-work/SKILL.md` and references** — S

   - Document `report`, the telemetry log, and the fact that queue status is now derived.

6. **Add unit tests** — M

   - Test `aet-state derive` against mocked git/fs states.
   - Test telemetry record generation and append behavior.

7. **Merge branch to main and verify integration** — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Dependencies

- Task 1 (schema) blocks Task 2 (`aet-state`).
- Task 2 blocks Task 6 (tests for derive).
- Task 3 (telemetry) blocks Task 4 (`report`) and Task 6 (tests for telemetry).
- Task 5 (docs) can happen after Tasks 2-4.

## Files to Modify

| File                                          | Change                                                   |
| --------------------------------------------- | -------------------------------------------------------- |
| `scripts/aet-state.py`                        | Create. Standalone state derivation and transitions.     |
| `aet-work/lib/telemetry.py`                   | Create. Telemetry log writer and schemas.                |
| `aet-work/SKILL.md`                           | Update. Document `report`, derived state, telemetry log. |
| `aet-work/references/telemetry-log-schema.md` | Create. Reference doc for log schema.                    |
| `scripts/test-aet-state.py`                   | Create. Unit tests for state derivation.                 |
| `scripts/test-telemetry.py`                   | Create. Unit tests for telemetry module.                 |

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `python3 scripts/test-aet-state.py` passes
- [ ] `python3 scripts/test-telemetry.py` passes
- [ ] For each new source file introduced by this plan, name the test that will cover it
  - `scripts/aet-state.py` → `scripts/test-aet-state.py`
  - `aet-work/lib/telemetry.py` → `scripts/test-telemetry.py`
- [ ] Distinguish test types: unit tests (single layer), integration tests (cross-layer), API boundary tests (frontend ↔ backend contract)
  - All tests in this plan are unit tests.
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

1. Revert the branch merge.
2. Restore previous `aet-work/SKILL.md` from git history.
3. Delete new files: `scripts/aet-state.py`, `aet-work/lib/telemetry.py`, `aet-work/references/telemetry-log-schema.md`, `scripts/test-aet-state.py`, `scripts/test-telemetry.py`.
4. Re-run `make validate` to confirm baseline.

---

_Stage: plan-approved_
_Next step: run `aet-work run --plan-file docs/plans/aet-state-telemetry-foundation-plan.md`_

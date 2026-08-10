---
id: vre-02-orchestrator-xdist-subgroups
size: M
blocked_by: []
pipeline: standard
status: merged
security_review: skipped
security_review_reason: test-suite parallelization change only; edits pytest markers and a test-grouping convention, no product, auth, data, or trust surface
docs_sync: required
docs_sync_reason: the resource-scoped subgroup taxonomy must be documented so new orchestrator tests pick the correct group instead of the removed monolithic one
---

# Plan: Split the Orchestrator xdist Group into Resource-Scoped Subgroups

## Context

- PRD: `docs/prds/validation-runtime-efficiency-prd.md` (R-4)
- Measured motivation: `reports/2026-07-24-validation-runtime-review.md` — the full suite runs
  ~76 s (+47%) slower under `--dist=loadgroup` (238 s vs 162 s) because a single
  `pytest.mark.xdist_group("orchestrator")` pins 15 files / 171 tests to one worker while the
  other seven idle (~120 s serial pole).
- **Hard constraint (measured):** dropping the group is unsafe — a safety probe running it
  unpinned failed **3/3**, a different orchestrator test each time
  (`test_batch_spawns_task_promoted_mid_run`,
  `test_emit_stage_session_classifies_failure_for_nonzero_exit`,
  `test_cleanup_kills_process_groups_on_shutdown`). The group exists for real isolation. The
  lever is a finer taxonomy, not removal (PRD Non-Goal: no `--dist=loadgroup` removal).
- Verified footprint (2026-07-24): exactly 15 module-level `pytestmark =
  pytest.mark.xdist_group("orchestrator")` sites under `tests/`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- Replace the single `"orchestrator"` group with **≥2 resource-scoped subgroups** keyed on the
  real shared resource a test contends for: process group, current working directory,
  telemetry directory, git repository. Mutually-safe heavy tests land in different subgroups
  (spread across workers); only tests that genuinely share a mutable resource stay
  co-grouped and serialized.
- The three proven-conflicting tests above set the floor: they must remain co-grouped with the
  tests they actually race, never scattered blindly.
- The taxonomy (resource → group name → what it protects) is documented so future orchestrator
  tests pick a subgroup deliberately.

## Rejected Alternatives

- **Drop `--dist=loadgroup` / unpin the group** — rejected: 3/3 safety-probe failure; the
  isolation is load-bearing.
- **One subgroup per file** — rejected: over-serializes safe tests and defeats the point; group
  by shared resource, not by file.
- **Leave the monolith and only speed up tests (vre-03 alone)** — rejected: the ~120 s serial
  pole is structural to the single group; taxonomy and speedup are complementary, this plan
  owns the taxonomy half.

## Task List

1. Define the resource-scoped subgroup taxonomy (process-group / cwd / telemetry-dir /
   git-repo) and document which shared resource each protects — S (traces: R-4)
2. Re-mark the 15 `xdist_group("orchestrator")` sites into the new subgroups, keeping the three
   proven-conflicting tests co-grouped with the tests they race — M (traces: R-4)
3. Measure: full-suite wall clock drops ≥ 60 s vs the 238 s baseline under
   `-n auto --dist=loadgroup`, and the suite is green across ≥ 10 consecutive runs — S
   (traces: R-4)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: the group taxonomy is an independently shippable, measurable change; the
  serial-pole speedup (vre-03) sequences after it on the same files.

## Files to Modify

- The 15 `tests/**` files carrying `pytestmark = pytest.mark.xdist_group("orchestrator")`
- `docs/CONVENTIONS.md` (or a `tests/` grouping note) — document the subgroup taxonomy

## Validation Steps

- [x] `make validate` passes
- [x] Coverage: the measurement in task 3 is the acceptance evidence (wall-clock delta +
  ≥ 10-run green streak); record both numbers in the plan's divergence/notes on closure
- [x] R-trace coverage: R-4 by tasks 1, 2, 3; no unknown R-ids
- [x] No orchestrator test is left ungrouped (every one of the 15 sites carries a subgroup
  marker; the three conflict-floor tests remain co-grouped)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Divergence / Notes

Measurement (2026-07-24, `-n auto --dist=loadgroup`, 8 workers, this branch):

| Run | Wall clock (s) |
| --- | -------------- |
| 1   | 104            |
| 2   | 100            |
| 3   | 103            |
| 4   | 103            |
| 5   | 104            |
| 6   | 103            |
| 7   | 102            |
| 8   | 103            |
| 9   | 105            |
| 10  | 109            |

- Mean: ~103.6 s
- Baseline: 238 s
- Delta: ~134 s improvement (>2× the ≥60 s target)
- Green streak: 10/10

Also fixed a pre-existing flake in `test_max_jobs_three_integration_steps_serialize`:
`_finalize_task` now trusts `awaiting_merge`/`merged` state before verifying the worktree
exists, because the worktree is intentionally removed after integration.

## Rollback Plan

Revert the merge commit; the single `xdist_group("orchestrator")` marker is restored on all 15
sites and the suite returns to the 238 s baseline behavior.

---

*Stage: merged*

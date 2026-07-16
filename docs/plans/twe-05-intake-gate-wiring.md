---
id: twe-05-intake-gate-wiring
size: M
blocked_by:
  - twe-04-plan-validate-suite
  - twe-01-work-class-attribute
pipeline: standard
security_review: required
security_review_reason: this is the enforcement wall — it makes a failing, un-acked plan unable to enter the queue through any intake path. A bypass (a path that mutates the queue before validating, or an ack parsed too loosely) defeats the gate; fail-closed ordering (validate before mutate) on `add`/`init-queue`/`sync` must be verified.
docs_sync: required
docs_sync_reason: `aet-work add` gains validation it never had; `init-queue` and `sync` intake behavior changes. The "every door into the queue enforces the same bar" contract must be documented.
status: approved
---

# Plan: Intake-Gate Wiring — Validate Fail-Closed in `add` / `init-queue` / `sync`

## Context

- PRD: `docs/prds/roadmap-p4-two-human-ends-prd.md` (G2; R-6, and the intake-enforcement of R-7's `work_class` rule).
- Closes the asymmetry twe-04 leaves open: the validate suite exists but is advisory until every intake path runs it. A half-baked plan must not sneak in through `aet-work add`.
- **Ground truth (re-grounded 2026-07-15):** `aet-work/bin/add` performs **no** quality validation today — only a stage check (refuses `merged`/`abandoned`, `:126–129`) and a settled/duplicate check (`:170–179`). `intake_validation_errors` is called **only** from `aet-work/bin/init-queue:262`. `sync` reconciles but does not validate new plans. This plan routes all three through the twe-04 suite (which subsumes the standalone structural call), so structural + semantic gates share one enforcement point.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `add`, `init-queue`, and `sync` each run the twe-04 `plan_validate` suite on the plan(s) they are about to admit, **before** mutating the queue, and reject a failing, un-acked plan with a named fail-closed error that leaves the queue unmutated. A clean or fully-acked plan is admitted exactly as before.
- `init-queue`'s current standalone `intake_validation_errors` call is replaced by the full suite (structural + R-trace + acceptance + scope-ref), so no path enforces a weaker bar than another.
- The `work_class` closed-set rule (twe-01) rides in via the shared suite — an invalid `work_class` is now rejected at `add`/`init-queue`/`sync`, not only wherever `intake_validation_errors` happened to run before.
- **Ordering is the contract:** validate → (pass) mutate, or (fail) named error + no mutation. No path writes then validates.

## Rejected Alternatives

- **Validate only in `add`** — rejected: R-6 says *every* intake path; `init-queue` and `sync` are doors too, and leaving them open re-creates the asymmetry this plan closes.
- **Warn-but-admit on failure** — rejected: fail-closed is the phase's kernel rule (P3 steal 4); an advisory gate is not a wall.
- **Duplicate the suite invocation per binary** — rejected: one shared entry point (the twe-04 suite) keeps the three doors from drifting; each binary calls it, none re-implements it.

## Task List

1. Wire the `plan_validate` suite into `aet-work/bin/add` (validate-before-mutate, fail-closed named error) — S (traces: R-6)
2. Replace `init-queue`'s standalone `intake_validation_errors` call with the full suite — S (traces: R-6)
3. Wire the suite into `sync` for newly-admitted plans, preserving existing-entry reconciliation — S (traces: R-6)
4. Tests: `tests/test_intake_gate.py` (new) — M (traces: R-6, R-7, R-11)
5. Merge branch to main and verify integration — S [Deferred: runs at `aet-ship`]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] The three intake edits share one reason (route each door through the twe-04 suite) — batched within this plan, exactly as ewl-01 batched four SKILL.md edits
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with twe-04 — that plan must land the suite first (`blocked_by` edge); this plan only wires it

## Files to Modify

- `aet-work/bin/add`
- `aet-work/bin/init-queue`
- `aet-work/bin/sync`
- `tests/test_intake_gate.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_intake_gate.py`:
  - `test_add_rejects_failing_unacked_plan_queue_unmutated`
  - `test_init_queue_rejects_failing_unacked_plan`
  - `test_sync_rejects_failing_unacked_plan`
  - `test_add_admits_clean_or_fully_acked_plan`
  - `test_add_rejects_invalid_work_class` (R-7 enforced at `add`)
  - `test_validate_runs_before_any_mutation` (asserts fail path leaves queue byte-identical)
- [ ] R-trace coverage: R-6 by tasks 1–3; R-7 (intake enforcement) by task 4; R-11 (this slice) by task 4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. `init-queue` returns to its standalone structural call; `add`/`sync` return to no-validation. The twe-04 command still exists for manual use. No queue-format change, so no migration.

## Pipeline

`pipeline: standard` with `security_review: required` — the enforcement wall; review scrutinizes validate-before-mutate ordering on all three doors.

---

*Stage: qa-complete*
*Next step: run `aet-review`*

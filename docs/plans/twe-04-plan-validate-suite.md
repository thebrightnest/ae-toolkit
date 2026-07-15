---
id: twe-04-plan-validate-suite
size: M
blocked_by:
  - ewl-06-adversarial-rehearsal
pipeline: standard
security_review: skipped
security_review_reason: read-only validator — parses plan/PRD/ADR markdown and reports pass/fail; writes nothing and opens no network. It becomes an enforcement wall only once twe-05 wires it into the intake paths, where the fail-closed behavior is security-reviewed.
docs_sync: required
docs_sync_reason: new user-facing `aet plan validate` subcommand and the `⚠️ VALIDATE ACK` authoring convention; planners need both documented.
status: approved
---

# Plan: `aet plan validate` — Four-Family Check Suite + Ack Escape Hatch

## Context

- PRD: `docs/prds/roadmap-p4-two-human-ends-prd.md` (G2; R-4, R-5). This plan builds the **command and the checks**; wiring it into `add`/`init-queue`/`sync` as a fail-closed gate is twe-05 (R-6), split out because touching three intake binaries plus this suite exceeds one session.
- Mechanizes plan-quality checks that are prose today (the `aet-plan` skill's Check 4 R-trace and its Validation-strategy gate), turning them into code a planner can run before the plan ever reaches the queue.
- **Ground truth (re-grounded 2026-07-15):** structural checks already exist as `plan_parser.intake_validation_errors` (`aet-work/lib/plan_parser.py:342`) — id/filename match, unique id, `size ∈ {S,M,L}`, gate-routing keys, `blocked_by` resolvable, atomic-complexity limits. The ack precedent is `⚠️ ATOMIC OVERSIZED` in `plan_parser.validate_size` (`:259`, marker check at `:267`). Two-word dispatch follows `aet gate submit`: a `plan` exec row in `aet-work/bin/aet` `SUBCOMMANDS` → new `aet-work/bin/plan` with a `validate` subparser.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- New `aet-work/bin/plan` with a `validate [<plan>...]` subcommand (default: all `docs/plans/*.md`). One `plan` row added to `aet-work/bin/aet` `SUBCOMMANDS`.
- Check suite in `aet-work/lib/plan_validate.py`, four families:
  - **(a) Structural** — delegate to `plan_parser.intake_validation_errors` (no duplication).
  - **(b) R-trace coverage** — collect R-ids from the source PRD's Requirements (located via the plan's Context/frontmatter PRD reference) and the `(traces: R-n)` citations in the task list; an in-scope R-id with no covering task and no recorded deferral **fails**; a task citing an R-id absent from the PRD **fails**.
  - **(c) Acceptance-as-evidence** — each acceptance criterion describes observable behavior (not a restated task), and every new source file the plan introduces has ≥1 **named** test in its validation strategy.
  - **(d) Scope-reference resolution** — every `docs/adr/NNN` reference resolves to an existing ADR file; flagged domain terms resolve against `CONTEXT.md`.
- **Ack escape hatch (R-5):** a failing check is overridden only by an explicit `⚠️ VALIDATE ACK: <check-id> — <reason>` marker with a **non-empty reason**, per-check-id, never blanket. A reason-less ack does not override (fail-safe), mirroring `⚠️ ATOMIC OVERSIZED`.
- Exit non-zero with named per-check errors on any un-acked failure; exit 0 on a clean or fully-acked plan.

## Rejected Alternatives

- **Re-implement the structural checks instead of reusing `intake_validation_errors`** — rejected: one source of structural truth; the suite composes the existing function so `init-queue`'s standalone call (subsumed in twe-05) and `aet plan validate` never diverge.
- **Blanket `⚠️ VALIDATE ACK` that suppresses all checks** — rejected: an escape hatch must be narrow and reasoned; per-check-id with a mandatory reason keeps every bypass legible in the plan itself.
- **Fold intake wiring into this plan** — rejected: `add` + `init-queue` + `sync` + this suite + tests exceeds the single-session guardrail; twe-05 owns the wiring behind a `blocked_by` edge.

## Task List

1. Write `aet-work/lib/plan_validate.py`: the four check families composing `intake_validation_errors`, returning named per-check results — M (traces: R-4)
2. Add the ack escape hatch (`⚠️ VALIDATE ACK: <check-id> — <reason>`), per-check-id, reason-required — S (traces: R-5)
3. Write `aet-work/bin/plan` (`validate` subparser) and add the `plan` row to `aet-work/bin/aet` `SUBCOMMANDS` — S (traces: R-4)
4. Tests: `tests/test_plan_validate.py` (new) — M (traces: R-4, R-5, R-11)
5. Merge branch to main and verify integration — S [Deferred: runs at `aet-ship`]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with twe-05 — this is the read-only validator; twe-05 changes intake behavior in three binaries and is `blocked_by` this plan

## Files to Modify

- `aet-work/lib/plan_validate.py` (new)
- `aet-work/bin/plan` (new)
- `aet-work/bin/aet`
- `tests/test_plan_validate.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_plan_validate.py`:
  - `test_structural_delegates_to_intake_validation`
  - `test_rtrace_missing_covering_task_fails`
  - `test_rtrace_task_cites_unknown_rid_fails`
  - `test_acceptance_restating_task_fails`
  - `test_new_source_file_without_named_test_fails`
  - `test_unresolved_adr_reference_fails`
  - `test_clean_plan_passes`
  - `test_ack_with_reason_overrides_that_check`
  - `test_ack_without_reason_does_not_override`
  - `test_plan_validate_routed_through_aet_dispatcher` (subprocess)
- [ ] R-trace coverage: R-4 by tasks 1,3; R-5 by task 2; R-11 (this slice) by task 4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. `aet plan validate` is a new read-only command; removing it changes no intake behavior (that lands in twe-05), so rollback is inert.

## Pipeline

`pipeline: standard` — a new read-only validator; enforcement (and its security review) lives in twe-05.

---

*Stage: qa-complete*
*Next step: run `aet-review`*

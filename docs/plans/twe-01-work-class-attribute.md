---
id: twe-01-work-class-attribute
size: M
blocked_by:
  - ewl-06-adversarial-rehearsal
pipeline: standard
security_review: skipped
security_review_reason: adds an authored plan-time attribute plus intake validation of its value; no new writer, trust boundary, or network surface. Fail-safe by design — a missing or invalid value never becomes zero-review-eligible (missing → `unclassified`).
docs_sync: required
docs_sync_reason: `work_class` becomes a documented plan-frontmatter key; the CONTEXT.md glossary and `docs/PIPELINE.md` change from "work class = the Trivial/Normal/Critical routing tiers" to "work class = a recorded machine-readable attribute" — a user-facing authoring contract.
status: approved
---

# Plan: `work_class` — Recorded Plan-Time Attribute + Intake Validation

## Context

- PRD: `docs/prds/roadmap-p4-two-human-ends-prd.md` (G3; R-7, plus the `work_class` slice of the R-6 intake gate and the attribute R-8 reads).
- Foundational for the phase: the desk's risk score (twe-02, R-2) and the zero-review track-record reader (twe-06, R-8) both key on `work_class`. This plan only *records and validates* the attribute; nothing reads it for a decision yet.
- **Ground truth (re-grounded 2026-07-15, post P2/P3):** `work_class` appears nowhere in the toolkit today (grep clean) — genuinely new, not a rename. Frontmatter is parsed by `plan_parser.parse_frontmatter` (`aet-work/lib/plan_parser.py:86`); a task record is minted by `new_task_from_plan` (`:281`); intake validation lives in `intake_validation_errors` (`:342`), today called only from `aet-work/bin/init-queue:262`. The three tiers are `docs/PIPELINE.md`'s Trivial/Normal/Critical.
- Determinism over discretion (ADR-020): `work_class` is **authored**, never inferred. No heuristic auto-classification (Non-Goals). A missing value is `unclassified`, which twe-06 treats as never zero-review-eligible.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `plan_parser.parse_frontmatter` gains recognition of an optional `work_class` key ∈ `{trivial, normal, critical}`. `new_task_from_plan` copies it onto the task record (default `unclassified` when absent) so the ledger can later attribute a merge to a class.
- `intake_validation_errors` gains one rule: if `work_class` is present and not one of the three tiers, return a named error (`work_class must be one of trivial|normal|critical (got '<x>')`). **Absent is legal** and becomes `unclassified` — fail-safe, never an error. This rule is enforced wherever `intake_validation_errors` runs; twe-05 extends that to `add`/`sync`.
- Docs: the CONTEXT.md glossary entry for "work class" and `docs/PIPELINE.md` change to state work class is a stored, machine-readable task attribute (the tier value), not only a routing concept.

## Rejected Alternatives

- **Infer `work_class` from plan `size` or routing keys** — rejected: violates ADR-020 (authored, not inferred) and would silently make work zero-review-eligible without a human labeling it. Unknown risk must rank as unknown, not be guessed.
- **Reject a missing `work_class` at intake** — rejected: too invasive for a phase that ships zero-review OFF; every existing plan would fail intake. Missing → `unclassified` is the fail-safe that keeps the attribute optional while never granting eligibility.
- **Store `work_class` only on the task record, not validated at intake** — rejected: an unvalidated free-text value would reach the track-record reader (twe-06) and the risk score (twe-02); validating at the door keeps the downstream readers total over a closed value set.

## Task List

1. Add `work_class` parsing to `plan_parser.parse_frontmatter` and carry it onto the record in `new_task_from_plan` (default `unclassified`) — M (traces: R-7)
2. Add the closed-set `work_class` validation rule to `plan_parser.intake_validation_errors` (present-and-invalid → named error; absent → legal) — S (traces: R-7)
3. Update the "work class" glossary entry in `CONTEXT.md` and the tier description in `docs/PIPELINE.md` to record it as a stored machine-readable attribute — S (traces: R-7)
4. Tests: `tests/test_work_class_attribute.py` (new) — M (traces: R-7, R-11)
5. Merge branch to main and verify integration — S [Deferred: runs at `aet-ship`]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with twe-02/twe-06 — those *read* this attribute and are `blocked_by` it; distinct risk surface

## Files to Modify

- `aet-work/lib/plan_parser.py`
- `CONTEXT.md`
- `docs/PIPELINE.md`
- `tests/test_work_class_attribute.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_work_class_attribute.py`:
  - `test_valid_work_class_parsed_onto_task`
  - `test_absent_work_class_defaults_unclassified`
  - `test_invalid_work_class_rejected_at_intake`
  - `test_absent_work_class_is_not_an_intake_error`
- [ ] R-trace coverage: R-7 by tasks 1–3; R-11 (this slice) by task 4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. `work_class` is additive and optional; absent it, every plan behaves exactly as today (`unclassified`, never eligible), so nothing downstream breaks on rollback.

## Pipeline

`pipeline: standard` — schema + validation change with docs sync; no isolated-per-stage risk profile.

---

*Stage: implemented*
*Next step: run `aet-qa`*

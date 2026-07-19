---
id: tll-01-first-pass-rework-definitions
size: M
status: queued
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: Changes the clean-merge predicate that zero-review eligibility (`class_eligibility` → `is_clean_merge`) is computed from; a wrong verdict requirement silently mis-counts the track record that 7b will arm auto-merge on.
docs_sync: required
docs_sync_reason: Changes the canonical definition of "clean merge" that the desk reports; CONTEXT.md glossary gains first-pass merge and rework.
---

# Plan: Routing-Aware First-Pass + Rework Definitions (Desk Unified)

## Context

- PRD: `docs/prds/roadmap-p7a-telemetry-learning-loop-prd.md` (R-1, R-2, R-6).
- **Ground truth (2026-07-19, `5163272`):** `aet-work/lib/track_record.py:19` hardcodes `REQUIRED_VERDICT_KINDS = ("qa", "review", "cso", "sync-docs")`, so `is_clean_merge` (`track_record.py:138`) demands all four verdicts even when a plan legitimately routed a gate to `skipped`. The desk already implements the routing-aware rule locally — `_ALWAYS_REQUIRED_VERDICTS = ("qa", "review")` and `_GATE_ROUTING_KEYS = {"cso": "security_review", "sync-docs": "docs_sync"}` (`aet-work/bin/desk:44-50`), consumed by `_required_verdicts(plan_data)` (`desk:137-143`). Two definitions of "clean" exist; this plan leaves exactly one, in a lib module both consumers import.
- `plan_parser.py` owns the routing-key contract (`ROUTING_GATE_KEYS`, `plan_parser.py:328`) and the canonical frontmatter parser (`parse_frontmatter`). Settled task records carry `plan_file`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect (roadmap Phase 7a; PRD intake triage recorded)

## Locked design

- **One routing-aware required-verdict rule, in `plan_parser`.** Add `VERDICT_GATE_KEYS = {"cso": "security_review", "sync-docs": "docs_sync"}` and `required_verdict_kinds(plan_data: dict) -> list[str]` to `aet-work/lib/plan_parser.py`: always `qa` + `review`, plus each gated kind whose plan key is not `skipped` (missing key ⇒ required — the standing fail-safe).
- **`is_clean_merge` becomes routing-aware.** In `track_record.py`, `_required_verdicts_pass` takes the task's required kinds: parse the frontmatter of `task["plan_file"]` via `plan_parser.parse_frontmatter`; on missing/unreadable plan file, fall back to `REQUIRED_VERDICT_KINDS` (all four — preserves current behavior for legacy settled tasks). A routed-away gate is excluded from the requirement; its verdict file is neither demanded nor read.
- **Canonical rework count.** Add `rework_count(task, ...) -> int` to `track_record.py`: (a) repeated-stage count — for each stage name, stage telemetry records beyond the first (from `iter_telemetry_task_records`); plus (b) failed re-entry count — history transitions with `from == "failed"`. Refactor `_has_repeated_stage` and `_has_reentry_from_failed` to be `count > 0` predicates over the same counting core, so the boolean (used by `is_clean_merge`) and the integer (used by metrics) can never drift apart.
- **Desk delegates.** Delete `_GATE_ROUTING_KEYS`, `_ALWAYS_REQUIRED_VERDICTS`, and `_required_verdicts` from `aet-work/bin/desk`; import `required_verdict_kinds` from `plan_parser`. `class_eligibility` needs no edit — it flows through `is_clean_merge` and becomes routing-aware automatically, so `aet desk --eligibility` and the future `aet metrics` agree by construction.

## Rejected Alternatives

- **Put `required_verdict_kinds` in `track_record.py` instead of `plan_parser.py`** — rejected: the routing-key contract (`ROUTING_GATE_KEYS`, validation) already lives in `plan_parser`; the verdict-kind mapping is part of that contract, and `plan_parser` has no dependency on track_record (no import cycle either way).
- **Persist a `first_pass` flag on the task record at merge time** — rejected (PRD Open Question 1, resolved at scope-validation): retroactive derivation keeps 7a read-only; telemetry + history suffice because the evidence store overwrites old verdicts anyway.
- **Leave desk's local copy and only fix `track_record`** — rejected: two copies of the same rule is the docs↔code reality gap this program exists to kill; desk/metrics disagreement about "clean" is precisely the failure mode R-1 names.

## Task List

1. `plan_parser.required_verdict_kinds` + `VERDICT_GATE_KEYS` — S (traces: R-1)
2. `track_record`: routing-aware `_required_verdicts_pass` with fail-safe fallback for missing plans — M (traces: R-1)
3. `track_record.rework_count` + shared counting core behind `_has_repeated_stage` / `_has_reentry_from_failed` — M (traces: R-2)
4. Desk: delete local routing rule, import from `plan_parser` — S (traces: R-1)
5. Tests: `tests/test_track_record_routing.py` (new) — M (traces: R-6)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not near-identical additions
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot share a branch — tll-02/03/04 build on these definitions; this must land first, alone

## Files to Modify

- `aet-work/lib/plan_parser.py` (`VERDICT_GATE_KEYS`, `required_verdict_kinds`)
- `aet-work/lib/track_record.py` (routing-aware verdicts, `rework_count`, shared counting core)
- `aet-work/bin/desk` (delegate to `plan_parser`)
- `tests/test_track_record_routing.py` (new)

## Validation Steps

- [ ] `make validate` passes
- [ ] New/changed coverage — `tests/test_track_record_routing.py`:
  - `test_required_verdict_kinds_defaults_to_all_four`
  - `test_required_verdict_kinds_excludes_skipped_gates`
  - `test_is_clean_merge_clean_when_routed_away_gate_verdict_absent`
  - `test_is_clean_merge_still_requires_non_skipped_gates`
  - `test_is_clean_merge_missing_plan_file_fails_safe_to_all_four`
  - `test_rework_count_repeated_stage_records`
  - `test_rework_count_failed_reentry_transitions`
  - `test_rework_count_zero_for_single_pass_task`
  - `test_desk_eligibility_matches_shared_definition` (desk `--eligibility` count equals the shared predicate over the same fixtures)
- [ ] R-trace coverage: R-1 by tasks 1, 2, 4; R-2 by task 3; R-6 by task 5; no unknown R-ids
- [ ] Test types: unit (verdict rule, rework counters) + integration (clean-merge over synthetic history + telemetry + evidence, desk agreement)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. `is_clean_merge` returns to requiring all four verdict kinds and the desk keeps its local copy; no stored data changes (definitions are computed read-side, nothing was persisted).

## Pipeline

`pipeline: standard` — touches the merge-governance predicate; standard grouping (TDD→implement→QA, review, CSO) is warranted.

---

*Stage: implemented*
*Next step: run `aet-qa`*

---
id: frh-12-retro-learning-candidates
size: S
blocked_by: []
pipeline: standard
---

# Plan: aet-retro Emits Learning-Candidate Telemetry

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G6)
- Owner decision (2026-07-09): `learning_candidate_record` is emitted by `aet-retro` (the retro already runs code-assisted and produces learnings), completing the deterministic + derive telemetry split.

`learning_candidate_record` (`lib/telemetry.py:339-360`) has zero call sites, yet `mine-learnings` mines that record type. `aet-evolve/bin/aet-retro` already maintains local copies of `derive_project_slug`/`read_jsonl` (skill directories cannot import `aet-work/lib`), so it appends records with its local helpers using the same archive layout (`~/.aet/telemetry/{slug}/...`).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. `aet-evolve/bin/aet-retro`: when a retro produces learnings/action items, append one `learning_candidate` record per item (fields per the `lib/telemetry.py` builder: `pattern_type`, `description`, `evidence`, `confidence`) to the telemetry archive under the current project slug — M
2. `docs/telemetry-guide.md`: add the learning-candidates line to "What gets recorded" (emitted by `aet-retro`) — S
3. Tests: `tests/test_aet_retro_telemetry.py` (new) — S
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines (marginal — kept separate because it lives in a different skill directory than any other frh plan)
- [x] Cannot share a branch with related tasks

## Files to Modify

- `aet-evolve/bin/aet-retro`
- `docs/telemetry-guide.md`
- `tests/test_aet_retro_telemetry.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_aet_retro_telemetry.py`:
  - `test_retro_emits_learning_candidate_records` (fixture retro input → valid records in a tmp `AET_TELEMETRY_ARCHIVE_DIR`)
  - `test_learning_candidate_records_parse_with_mine_learnings`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; the archive is append-only JSONL, unknown types are skipped by readers.

---

_Stage: plan-approved_
_Next step: run `aet-work`_

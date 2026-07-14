---
id: ttf-03-structural-pattern-mining
size: M
blocked_by:
  - ttf-01-wire-test-run-extraction
pipeline: standard
status: approved
security_review: skipped
security_review_reason: read-only aggregation of local telemetry JSONL; no untrusted input executed, no network, no new trust boundary, no data mutation (analysis path only)
docs_sync: skipped
docs_sync_reason: the `test_run`/`stage` record fields this plan reads are documented by ttf-01's telemetry-log-schema.md; mine-learnings' own pattern vocabulary is not enumerated in any reference doc today, so there is nothing to keep in sync
---

# Plan: Structural Pattern Mining for mine-learnings / aet retro

## Context

- PRD: `docs/prds/test-telemetry-fidelity-prd.md` (R-4, R-5, R-6).
- `mine-learnings` derives `full_suite_runs` **only** from the narrative
  markdown keyword scan (`NARRATIVE_PATTERNS`, `aet-evolve/bin/mine-learnings:82-92`,
  including the stale `"488-test"` keyword at line 89). Since reports moved to
  JSON, `reports_scanned` is 0 across the archive, so `full_suite_runs` is
  permanently 0 (PRD: "0 reports scanned across 102 runs").
- The `stage` branch (`mine-learnings:234-238`) inspects only `exit_code` and
  `stage == "review"`; each `stage` record's `duration_seconds`
  (`telemetry.py:stage_record`, line 213) and `token_count` (line 219) are
  ignored, so no slow-stage / token-burn detection exists.
- `test_run` records (`telemetry.py:test_run_record`) already carry `scope`
  (line 314) and `duration_seconds` (line 318). Once ttf-01 lands, real
  per-invocation records with a classified `scope` exist to count structurally.
- `aet-retro` embeds `mine-learnings --propose` stdout verbatim into its
  "## Telemetry Summary" fenced block (`aet-evolve/bin/aet-retro:212-222` and
  `:298-302`), so new counts surface in the retro automatically once
  mine-learnings emits them — no retro rendering change is required.
- Live archive today: 120/120 `stage` records carry duration, of which **21
  exceed 1800s and 7 exceed 5,000,000 tokens** — slow_stage/token_burn fire
  immediately. 37 `test_run` records exist (verdict-gate, hardcoded scope);
  their `scope` becomes trustworthy only after ttf-01/ttf-02.
- Depends on ttf-01 for real `scope`-classified `test_run` records (the count
  inputs) and the shared scope vocabulary; without it only verdict-gate records
  exist.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
      (folds in one defect repair — the dead `full_suite_runs` keyword scan —
      mirroring the ttf-02 / PRD precedent)

## Locked design

- **Structural test-scope counting (R-4).** In `mine_archive`, aggregate
  `test_run` records by `record["scope"]`: `scope == "full-suite"` →
  `full_suite_runs`; `scope == "impact"` → new `impact_runs`; `unknown` is left
  uncounted in these two. Tally `repeated_test_invocations` deterministically:
  group `test_run` records by `task_id`, and sum `max(0, full_suite_count − 1)`
  per task — i.e. the number of **redundant** full-suite runs (the "ran the
  full suite five times or twice" signal).
- **Retire the narrative scan for the covered category (R-4).** Remove the
  `full_suite_runs` tuple from `NARRATIVE_PATTERNS` (`mine-learnings:82-92`,
  dropping the stale `"488-test"` keyword list); the category is now structural.
  The other narrative categories (`dependency_issues`, `repeated_loops`,
  `stage_failures`, `review_noise`) are untouched — out of scope.
- **Slow-stage & token-burn flags (R-5).** In the `stage` branch, add:
  `duration_seconds > SLOW_STAGE_THRESHOLD_S` → `slow_stage`;
  `token_count is not None and token_count > TOKEN_BURN_THRESHOLD` →
  `token_burn`. Thresholds are module-level tunable constants:
  `SLOW_STAGE_THRESHOLD_S = 1800`, `TOKEN_BURN_THRESHOLD = 5_000_000`
  (PRD-proposed; revisit after one week of data).
- **Report + propose (R-6).** `format_report` (`mine-learnings:272-318`) lists
  the new counts (full-suite / impact / repeated / slow_stage / token_burn).
  `propose_edits` (`mine-learnings:321-355`) maps each new nonzero count to a
  skill-edit suggestion (full-suite/repeated → aet-qa/aet-implement
  impact-scoping; slow_stage → stage-time triage; token_burn → prompt/scope
  trimming). `aet-retro` needs no code change; its Telemetry Summary is verified
  by test.
- **No record-schema change.** This plan only reads existing fields; the
  `test_run.scope` vocabulary and null contract are owned and documented by
  ttf-01.

## Rejected Alternatives

- **Re-point the narrative keyword scan at the JSON reports instead of counting
  structurally** — rejected: the keyword lists are already stale (`"488-test"`)
  and lossy; structural counts from `scope` are exact and auditable (PRD:
  structural detection is strictly better).
- **Expose the slow/token thresholds as CLI flags** — rejected: they are tuning
  constants that must stay consistent across runs and versioned; module
  constants keep runs comparable. Revisit after a week of data.
- **Compute `token_burn` from the run-level `total_tokens` record** — rejected:
  R-5 scopes the flag to per-`stage` `token_count` so a single hot stage is
  attributable; run-level aggregation hides which stage burned.
- **Render a structured (non-embedded) summary in `aet-retro`** — rejected: it
  already embeds `mine-learnings --propose` verbatim; a parallel renderer
  duplicates the source of truth.

## Task List

1. `mine-learnings`: structural `full_suite_runs` + `impact_runs` +
   `repeated_test_invocations` from `test_run` records; retire the
   `full_suite_runs` narrative pattern — M (traces: R-4)
2. `mine-learnings`: `slow_stage` + `token_burn` from `stage` records with
   tunable threshold constants — S (traces: R-5)
3. `mine-learnings`: surface the new counts in `format_report` and map them to
   suggestions in `propose_edits` — S (traces: R-4, R-5, R-6)
4. `tests/test_mine_learnings.py`: fixtures — full-suite/impact/unknown
   `test_run` counting, repeated-invocation tally per task, slow_stage and
   token_burn boundary cases, and proof the retired `"488-test"` narrative
   keyword no longer counts — M (traces: R-4, R-5)
5. `tests/test_aet_retro.py`: assert the Telemetry Summary embeds the new
   counts and `--propose` references them — S (traces: R-6)
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks (blocked_by ttf-01;
      consumes its scope-classified `test_run` records).

## Files to Modify

- `aet-evolve/bin/mine-learnings`
- `tests/test_mine_learnings.py`
- `tests/test_aet_retro.py`

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`python3 -m pytest tests/test_mine_learnings.py tests/test_aet_retro.py -q`, then full suite before commit)
- [ ] Unit: `test_mine_learnings.py` covers full-suite/impact/unknown counting, per-task repeated-invocation tally, slow_stage/token_burn boundaries, and the retired `"488-test"` keyword contributing 0
- [ ] Integration: `test_aet_retro.py` proves the retro Telemetry Summary renders the new counts and `--propose` cites them
- [ ] Live check: `aet mine-learnings` on the real archive reports the existing `slow_stage` (~21) and `token_burn` (~7) counts immediately, and nonzero full-suite/impact counts once ttf-01 wire records exist
- [ ] R-trace coverage: R-4, R-5, R-6 all covered; no unknown R-ids cited
- [ ] No `full_suite_runs` keyword tuple remains in `NARRATIVE_PATTERNS`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. `mine-learnings` reverts to the narrative-only counts
(`full_suite_runs` → 0 as before) and drops the slow/token flags; telemetry
records are read-only throughout, so no data is mutated and already-written
records stay valid.

## Pipeline

`standard` — read-only aggregation across `mine-learnings` and the retro embed;
no auth/data-model/API surface. Could run `minimal`; kept `standard` for the
review pass on the analysis path (matches ttf-02's rationale).

---

_Stage: reviewed_

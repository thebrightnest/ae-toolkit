---
id: ttf-02-verdict-scope-classification
size: S
blocked_by:
  - ttf-01-wire-test-run-extraction
pipeline: standard
status: approved
security_review: skipped
security_review_reason: value-only change at a telemetry emission site; no parsing of untrusted input beyond the existing verdict read, no new trust boundary
docs_sync: skipped
docs_sync_reason: schema vocabulary and null contract for these records are documented in ttf-01; this plan only stops fabricating values into existing fields
---

# Plan: Verdict-Derived test_run Scope Classification & Honest Nulls

## Context

- PRD: `docs/prds/test-telemetry-fidelity-prd.md` (R-2, R-3).
- `_emit_test_run_from_verdict` (`aet-work/bin/orchestrator:369`) derives the
  one `test_run` record per QA gate from the verdict file and currently
  hardcodes `scope="full-suite"` (line 384) and sets
  `start_time == end_time == verdict.generated_at`, yielding
  `duration_seconds: 0.0`. Across the live archive: 14/14 records
  `full-suite`, 14/14 duration 0 — scope statistics are unusable until this
  stops.
- Depends on ttf-01 for the shared `classify_test_scope` helper and the
  nullable-timestamp `test_run_record`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
      (defect repair folded into this enhancement plan per PRD intake note)

## Locked design

- Replace the literal with
  `scope=telemetry.classify_test_scope(record.get("test_command", ""))`.
- Pass `start_time=None, end_time=None` so duration records `None` (verdicts
  carry a single `generated_at`; the gate never measured the run). Keep
  `exit_code=0` and the tests_total/passed/failed fields from the verdict —
  those are measured.
- No new record fields; no verdict-schema change.

## Rejected Alternatives

- **Drop the verdict-derived record entirely once wire records exist** —
  rejected: wire extraction only covers kimi sessions; the verdict record is
  the CLI-agnostic floor and carries measured pass/fail counts.
- **Have the QA skill write a duration into the verdict** — rejected: verdict
  contract change owned by the ewl/gate-evidence line of work; out of scope
  here, and unneeded once wire records exist for kimi.
- **Leave duration at 0.0 for backward compatibility** — rejected: 0.0 is
  indistinguishable from a real instant run and silently corrupts duration
  aggregates; `null` is the schema's honest value.

## Task List

1. Orchestrator: classified scope + null timestamps in
   `_emit_test_run_from_verdict` — S (traces: R-2, R-3)
2. Tests: extend `tests/test_orchestrator.py` (or the verdict-emission test)
   — verdict with `make validate` command → `full-suite`, verdict with
   `pytest tests/test_x.py` → `impact`, duration is `None`, totals preserved — S
   (traces: R-2, R-3)
3. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [ ] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks (blocked_by ttf-01;
      same helper, different emission site — merging would make ttf-01 an L).

## Files to Modify

- `aet-work/bin/orchestrator`
- `tests/test_orchestrator.py`

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (targeted orchestrator tests, then full suite before commit)
- [ ] Named coverage: the verdict-emission test asserts scope classification and `duration_seconds is None`
- [ ] R-trace coverage: R-2, R-3 covered; no unknown R-ids cited
- [ ] No `scope="full-suite"` literal remains in `aet-work/bin/orchestrator`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Records revert to the old fabricated values on the
next run; existing JSONL lines are append-only and untouched.

## Pipeline

`standard` — two files, no security surface; could run `minimal`, kept
`standard` for the review pass on the gate path.

---

_Stage: plan-approved_
_Next step: run `aet-work`_

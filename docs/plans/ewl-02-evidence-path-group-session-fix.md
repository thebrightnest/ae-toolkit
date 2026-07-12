---
id: ewl-02-evidence-path-group-session-fix
size: S
blocked_by:
  - cli-03-skills-lint
pipeline: standard
status: abandoned
security_review: skipped
security_review_reason: surgical env-var export fix inside the existing orchestrator evidence-gate path; no new writer, no new trust boundary — frh-11 already established this exact pattern for run_stage
docs_sync: skipped
docs_sync_reason: internal orchestrator bugfix with no user-facing surface change; existing docs already describe both run_stage and run_stage_group as exporting AET_EVIDENCE_PATH — code is catching up to already-documented intent, not introducing new behavior to document
---

# Plan: Fix `AET_EVIDENCE_PATH` Derivation in `run_stage_group`

> **ABANDONED — duplicate.** Superseded by `docs/plans/frh-18-group-evidence-path-contract.md`, already `status: approved` and queued (`ready`) before this plan reached `aet-work add`. frh-18 targets the identical root cause (confirmed same functions/line ranges in `aet-work/bin/orchestrator`) with a materially more correct design: a per-kind `AET_EVIDENCE_PATH_<KIND>` precedence, which this plan's single flat `AET_EVIDENCE_PATH` does not handle correctly when a group session runs more than one evidence-bound stage concurrently (e.g. a `[reviewed, secure]` group — the exact scenario this plan's own regression test named). frh-18 also adds gate-diagnostics and an ADR this plan didn't scope. Never added to the work queue; nothing to `mark-terminal`. Kept on disk, unqueued, for the paper trail — see `ewl-01`'s Context for the resulting `blocked_by` change.

## Context

- PRD: `docs/prds/roadmap-p3-enforcement-walls-prd.md` (G1; R-3, plus R-8 tests)
- Confirmed by direct inspection, not assumed from the roadmap prose: `aet-work/bin/orchestrator`'s `run_stage` (`:390`) sets `AET_EVIDENCE_PATH` at `:414`; `run_stage_group` (`:454`) does not. Under batch/group-session concurrency, a stage running inside a group session falls back to a CWD-derived project-slug path that can diverge from the path frh-11's evidence gate actually reads.
- This is the confirmed root cause of the `thp-04` incident recorded in `.agents/learnings.jsonl`: a fully-completed, verified task was marked failed three times because its verdict landed at a different path than the gate checked.
- Independent of the new `aet gate submit` surface (ewl-01) — this is a pre-existing bug in already-merged frh-11 code, reachable regardless of which writer produces the verdict.

## Intake Triage

- [x] Confirmed this is a **reproducible defect** (thp-04) being fixed as part of a planned enforcement-walls pass, not filed separately via `aet-bug-report`, because the PRD (G1) explicitly scopes it as part of "gate submission is centralized and fail-closed" — the fix belongs with the rest of the verdict-path work it shares a root cause with.

## Locked design

- In `run_stage_group`, before invoking each evidence-bound stage, compute and export `AET_EVIDENCE_PATH` using the identical derivation `run_stage` uses at `:414` (same `evidence.evidence_path()` call, same project-slug/task-id inputs) — not a new derivation, a call-site parity fix.
- No change to `run_stage`, to `evidence.py`, or to the fallback CWD-derived path itself — the fallback remains correct for contexts with no orchestrator-managed path (e.g., a lone manual invocation); the bug is specifically that `run_stage_group` never gets far enough to set the primary path before stages run.

## Rejected Alternatives

- **Remove the CWD-derived fallback entirely, requiring `AET_EVIDENCE_PATH` always be pre-set** — rejected: the fallback is a legitimate degradation path for out-of-orchestrator invocations (e.g., a developer running a checking skill by hand); removing it would break that case instead of fixing the actual bug, which is `run_stage_group` never populating the env var it should.
- **Bundle with ewl-01** — rejected: this is a bugfix to already-merged frh-11 code with a different risk profile and no dependency on the new `gate submit` binary; keeping it separate lets it merge on its own schedule without waiting on ewl-01's security review.

## Task List

1. In `aet-work/bin/orchestrator`'s `run_stage_group`, export `AET_EVIDENCE_PATH` per evidence-bound stage the same way `run_stage` does at `:414` — S (traces: R-3)
2. Regression test reproducing the thp-04 scenario: a concurrent group-session batch (e.g., a `[reviewed, secure]`-style stage group) writes verdicts, asserting both land at the path the evidence gate reads, with no CWD-derived-slug divergence — M (traces: R-3, R-8)
3. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition — a single-site bugfix
- [x] Diff expected ≤ 30 lines / 2 files — genuinely small, not artificially split from a larger unit
- [x] Cannot share a branch with ewl-01 — different risk profile (bugfix to merged code vs. new writer surface)

## Files to Modify

- `aet-work/bin/orchestrator`
- `tests/test_orchestrator.py`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New/extended coverage — `tests/test_orchestrator.py`:
  - `test_run_stage_group_sets_evidence_path` — unit: asserts `AET_EVIDENCE_PATH` is present in the stage's env and matches `evidence.evidence_path()`'s output for the same inputs `run_stage` would use
  - `test_run_stage_group_concurrent_batch_no_path_divergence` — integration: reproduces the thp-04 shape (concurrent group-session stages), asserts every verdict is found by the gate at the path it was written to
- [ ] R-trace coverage: R-3 by tasks 1–2; R-8 by task 2; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — `run_stage_group` returns to CWD-derived-fallback behavior; the thp-04 failure mode returns but is neither new nor worse than pre-existing behavior.

## Pipeline

`pipeline: standard`.

---

_Stage: abandoned_
_Next step: none — superseded by `frh-18-group-evidence-path-contract`_

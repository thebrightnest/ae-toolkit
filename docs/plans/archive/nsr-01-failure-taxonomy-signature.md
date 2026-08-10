---
id: nsr-01-failure-taxonomy-signature
size: M
blocked_by:
  - twe-07-exit-gate-rehearsal
pipeline: standard
status: merged
security_review: skipped
security_review_reason: pure classification/hashing module over already-captured session output; no new writer, network, secret, or trust boundary. Signatures are one-way digests, not executed.
docs_sync: skipped
docs_sync_reason: internal library with no user-facing surface until nsr-04 wires `--on-failure`; the taxonomy is documented (CONTEXT.md/PIPELINE.md) at the point it becomes observable, in nsr-04.
---

# Plan: Failure Taxonomy + Normalized Signature (`lib/failure.py`)

## Context

- PRD: `docs/prds/roadmap-p5-night-shift-runtime-prd.md` (G1; R-1, R-2).
- Foundation for the phase: the circuit breaker (nsr-03) counts signatures, the triage router (nsr-04) branches on the class, and the stall watchdog (nsr-05) emits the `timeout` class. This plan ships the pure classifier + signature only — **no orchestrator wiring** (that is nsr-04/05).
- **Ground truth (2026-07-15):** no failure classification exists today — the finalize path (`_mark_failed`, `aet-work/bin/orchestrator:1125`) transitions straight to `failed` with no taxonomy. The signals the classifier needs are already captured: exit code (`proc.wait()`), the bounded tail from `_run_with_live_tee` (`:536`, ~256 KB), the stage, and whether a required verdict was recorded (`_require_passing_verdict`, `:492`). The shutdown flag `_shutdown_requested` (`:60`) marks the `canceled` case.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- New pure module `aet-work/lib/failure.py`, no orchestrator import back-edges:
  - `classify(*, exit_code, tail, stage, verdict_recorded, shutdown, killed_by_timeout) -> FailureClass` returning one of `environment | flaky | design | timeout | canceled`. Precedence is explicit and total: `shutdown → canceled`; `killed_by_timeout → timeout`; then tail-pattern partitions `environment` (tool/dep/network/auth signatures) vs `design` (test/assertion/type/lint failure with a recorded fail verdict) vs `flaky` (non-zero exit with no stable error signal); the **fail-safe default is `environment`** (retry-eligible, breaker-bounded — resolves PRD Open Question 1, pending scope-validation).
  - `signature(*, stage, tail) -> str`: lower-cased error key extracted from the tail, with volatile spans normalized out — absolute/relative paths, PIDs, ISO/epoch timestamps, hex and UUIDs, and `line:col` numbers replaced by fixed placeholders — then `sha1(f"{stage}\n{error_key}")[:12]`. Same deterministic failure ⇒ same signature; different stage or error class ⇒ different signature.
- Both functions are total and side-effect-free; all inputs are plain values so tests need no live session.

## Rejected Alternatives

- **Classify from the exit code alone** — rejected: exit codes are near-uniformly `1`; they cannot separate a missing-dependency environment failure from a genuine test failure. The tail carries the discriminating signal.
- **LLM-classify the failure** — rejected: violates ADR-020 determinism and makes the breaker's counting non-reproducible; a signature must be a pure function so identical failures always collide. (nsr-04's triage session *confirms* a class for the requeue/quarantine decision, but the breaker's counting key stays deterministic.)
- **Hash the raw tail as the signature** — rejected: volatile spans (paths, PIDs, timestamps) would make every failure unique, defeating the 3×-same-signature breaker. Normalization is the whole point.

## Task List

1. Create `aet-work/lib/failure.py` with the `FailureClass` enum and `classify(...)` (total precedence, `environment` fail-safe default) — M (traces: R-1)
2. Add `signature(...)` with volatile-span normalization + stage-scoped digest to `failure.py` — M (traces: R-2)
3. Tests: `tests/test_failure_taxonomy.py` (new) — M (traces: R-1, R-2, R-13)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch — nsr-03/04/05 *consume* this module and are `blocked_by` it; distinct surface

## Files to Modify

- `aet-work/lib/failure.py` (new)
- `tests/test_failure_taxonomy.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_failure_taxonomy.py` covers `aet-work/lib/failure.py`:
  - `test_classify_each_category` (environment/flaky/design/timeout/canceled)
  - `test_classify_shutdown_is_canceled`
  - `test_classify_ambiguous_defaults_environment`
  - `test_signature_stable_across_volatile_spans` (paths/PIDs/timestamps/line numbers)
  - `test_signature_distinct_across_stage_and_error_class`
- [ ] R-trace coverage: R-1 by tasks 1; R-2 by task 2; R-13 (this slice) by task 3; no unknown R-ids
- [ ] Distinguish test types: all unit tests (single pure module)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The module is standalone and imported by nothing until nsr-04/05; removing it affects no runtime path.

## Pipeline

`pipeline: standard` — a new library module with unit tests; no isolated-per-stage risk profile.

---

*Stage: merged*
*Next step: run `aet-work`*

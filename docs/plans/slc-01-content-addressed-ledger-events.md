---
id: slc-01-content-addressed-ledger-events
size: M
work_class: critical
blocked_by: []
pipeline: standard
status: queued
security_review: required
security_review_reason: touches the persisted state store and its integrity model
docs_sync: required
docs_sync_reason: removes the tamper-evidence envelope contract documented in backend docstrings
---

# Plan: Content-Addressed Ledger Events and the Commutative Envelope

## Context

PRD: `docs/prds/single-ledger-closure-prd.md` (R-2, R-3). ADR-055. Foundation
plan: ships the provenance event store every other slc plan wires into.
The git-refs backend (`src/aet/backends/git_refs_backend.py`) already stores
per-task blobs at `refs/aet/tasks/<id>` with the envelope at
`refs/aet/meta/queue`; its chained `content_hash` (`:152`) and `StampMismatch`
refusal are non-commutative over a changing task-ref set and leave the
operational path here.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. New module `src/aet/ledger.py`: event schema — `kind` ∈ {`cut`, `stage`,
   `verdict`, `land`}, `ref_kind` ∈ {`git-sha`, `pr`, `plan-hash`,
   `evidence-path`}, deterministic id from
   `source:task:kind:(ref | occurred_at)`, `occurred_at` vs `created_at`
   split — M (traces: R-2)
2. Idempotent write path at the store boundary: duplicate ids are no-ops
   (INSERT-IGNORE semantics); events without a ref require an explicit
   caller-supplied `occurred_at`, rejected otherwise for every caller;
   reserved `ingest-backfill` source rejected on the write path — S (traces: R-2)
3. Remove the chained `content_hash` from the operational path: envelope
   carries a `schema_version` field instead; `StampMismatch` and its refusal
   path are deleted (warn-and-continue becomes the only degradation mode) — S
   (traces: R-3)
4. Emit events from the two existing choke points: `cut` at queue intake
   (`aet sprint add`), `land` at terminal closure — S (traces: R-2)
5. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: the event store is reviewable and testable without any
  consumer beyond the two choke points.
- [x] Expected diff (~400 lines + tests) materially exceeds PR overhead.
- [x] Cannot share a branch with slc-02 (sync is a separate behavior with its
  own failure modes).

## Rejected Alternatives

- **Absorb verdicts/evidence into the event payload** — rejected: the
  union-type lesson (beads' 60-field `Issue`); events reference external
  artifacts by hash/path only.
- **Keep the chained hash as an optional verification mode** — rejected: a
  chain over a set is non-commutative by construction; keeping it as an
  opt-in keeps the conflict generator alive (ADR-055).
- **Backfill `work-history.jsonl` into events** — rejected at scope
  validation: history is write-only telemetry; backfill fabricates
  provenance nobody observed. The `ingest-backfill` source stays reserved
  and unused.

## Files to Modify

- `src/aet/ledger.py` (new)
- `src/aet/backends/git_refs_backend.py`
- `src/aet/backends/base.py`
- `src/aet/cli/sprint.py` (cut emission)
- `src/aet/cli/ship.py` (land emission)
- `tests/ledger/test_ledger.py` (new)
- `tests/backends/test_git_refs_backend.py`

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`make test`)
- [ ] `tests/ledger/test_ledger.py` covers `src/aet/ledger.py`: deterministic
  ids, duplicate-write no-op, missing-`occurred_at` rejection,
  `ingest-backfill` rejection, `occurred_at`≠`created_at` (unit)
- [ ] Envelope round-trip carries `schema_version` and no `content_hash`;
  a hand-edited envelope no longer bricks reads (integration,
  `tests/backends/test_git_refs_backend.py`)
- [ ] R-trace coverage: R-2, R-3 covered by tasks 1–4
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. The event store is additive; the envelope change is the
only destructive part, and the pre-change envelope is recoverable from git
history (the refs themselves are untouched by a code revert).

## Pipeline

`standard` — persisted-state and integrity-model change (risk override per
ADR-047).

---

*Stage: qa-complete*
*Next step: run `aet-review`*

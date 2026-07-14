---
id: ewl-05-git-refs-tamper-evidence
size: M
blocked_by:
  - cli-03-skills-lint
  - uct-01-usage-cost-telemetry
pipeline: standard
security_review: required
security_review_reason: introduces the integrity/tamper-detection mechanism directly protecting the task ledger against out-of-band writes — the correctness of the detection logic is itself the security property this plan delivers
docs_sync: required
docs_sync_reason: new tamper-evidence behavior for git-refs needs the same documentation treatment frh-17 gave the JSON backend's queue guard
---

# Plan: git-refs Tamper-Evidence

## Context

- PRD: `docs/prds/roadmap-p3-enforcement-walls-prd.md` (G3; R-6, plus R-8 tests)
- **Mode-neutral by construction:** tamper-evidence operates on the `.git` refs (`refs/aet/tasks/*`, `refs/aet/meta/queue`) whether or not they are ever pushed, so it protects the ledger identically in Mode 1 (local, unpushed) and Mode 2 (shared). No change is needed here for the non-invasive scope; ewl-06's Mode-1 arm (d) / R-7c exercises this mechanism in a config-external checkout.
- frh-17 gave the JSON backend tamper-evidence: `write_queue` (`aet-work/lib/queue.py`) stamps a monotonic `revision` and a sha256 `content_hash` into the wrapper; `read_queue` verifies both and raises `QueueIntegrityError` on mismatch.
- Confirmed by direct inspection: `GitRefsBackend.seal()` (`aet-work/lib/backends/git_refs_backend.py`, frh-13) drops a task's ref and appends to history with **no equivalent integrity stamp**. This is a genuine gap, not mentioned explicitly in the roadmap's Phase 3 bullet list — surfaced during clarify-goal grounding and confirmed in-scope for this phase, because ewl-04 makes git-refs the default backend, and the PRD's exit gate (R-7b) requires a hand-edited ledger write to be mechanically detected on the backend that is actually the default once Phase 3 lands.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- Content-hash chaining across the envelope ref (`refs/aet/meta/queue`): each save recomputes a `content_hash` covering the prior hash plus the current task-ref set (task IDs + their blob OIDs), and stamps it into the envelope blob — mirroring frh-17's `revision`/`content_hash` semantics, chained rather than single-shot because the envelope is the one ref that observes the full task-ref set on every write.
- Read path (`GitRefsBackend.load`/equivalent) recomputes the expected hash from the current ref state and compares to the stamped value:
  - Mismatch on a **mutating** path (anything that will `seal`/write) → fail closed, raise a `GitRefsIntegrityError` (new, or a shared base with `QueueIntegrityError` if a common parent is a clean fit — implementer's call, not fixed here) before any write proceeds.
  - Mismatch on a **read-only** path (`aet state`, `aet status`, `aet report`) → warn and continue, mirroring frh-17's read-path contract of not blocking observability on a ledger that's already compromised.
- Legacy git-refs data written before this plan (unstamped) is accepted and stamped on first subsequent write — mirrors frh-17's own legacy-queue-acceptance behavior, so this plan doesn't brick an existing git-refs install mid-flight.
- A hand-edited task ref or envelope blob (content changed outside the backend's own write path) is detected the next time anything reads it — this is the concrete, buildable interpretation of the PRD's R-7b rehearsal.

## Rejected Alternatives

- **GPG-signed commits/refs for tamper-evidence** — rejected: explicit PRD Non-Goal; content-hash-based detection only, consistent with frh-17's existing approach. Identity/signature verification is a different, heavier guarantee than this phase needs.
- **A single unstamped hash per task ref, independent of the envelope** — rejected: doesn't detect a task ref being silently _removed_ from the set (only a per-ref content edit); chaining through the envelope's task-ref set catches both edits and removals/insertions.
- **Blocking reads on any mismatch, including observability commands** — rejected: matches frh-17's own rejected-alternative reasoning (a compromised ledger shouldn't also take down the ability to see that it's compromised); read-only paths warn and continue, exactly mirroring the JSON backend's existing contract.

## Task List

1. Design and implement content-hash chaining for `GitRefsBackend`'s save path (envelope blob at `refs/aet/meta/queue` carries the chained `content_hash`) — M (traces: R-6)
2. Implement the read-path verification: mutating paths fail closed with a new integrity-error type; read-only paths warn and continue; legacy unstamped data is accepted and stamped on next write — M (traces: R-6)
3. Tests: `tests/test_git_refs_tamper_evidence.py` (new) — hand-edit a ref/blob outside the backend API, assert detection on next read; assert legacy unstamped data is accepted and stamped; assert read-only paths warn-and-continue while mutating paths fail closed — M (traces: R-6, R-8)
4. Docs: extend `aet-work/SKILL.md` (or wherever frh-17's JSON queue-guard note lives) with the git-refs tamper-evidence equivalent — S (traces: R-6)
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition to anything queued
- [x] Diff expected > 3 files / > 100 lines (chaining logic + read-path verification + tests + docs)
- [x] Cannot share a branch with ewl-04 — independently revertible (see ewl-04's Rejected Alternatives)

## Files to Modify

- `aet-work/lib/backends/git_refs_backend.py`
- `aet-work/lib/backends/base.py` (only if a shared integrity-error base type is the clean fit — implementer's call per Locked design)
- `tests/test_git_refs_tamper_evidence.py` (new)
- `aet-work/SKILL.md`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_git_refs_tamper_evidence.py`:
  - `test_hand_edited_task_ref_detected_on_next_read`
  - `test_hand_edited_envelope_blob_detected_on_next_read`
  - `test_mutating_path_fails_closed_on_integrity_mismatch`
  - `test_read_only_path_warns_and_continues_on_integrity_mismatch`
  - `test_legacy_unstamped_data_accepted_and_stamped_on_next_write`
  - `test_clean_chain_round_trip_no_false_positive`
- [ ] R-trace coverage: R-6 by tasks 1–4; R-8 by task 3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — `GitRefsBackend.seal()`/read path return to no integrity stamping. Any refs/blobs stamped while this plan was live remain readable (stamp is additive metadata, not a required field old code paths depend on).

## Pipeline

`pipeline: standard`.

---

_Stage: qa-complete_
_Next step: run `aet-review`_

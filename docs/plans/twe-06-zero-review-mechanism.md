---
id: twe-06-zero-review-mechanism
size: M
blocked_by:
  - twe-01-work-class-attribute
pipeline: standard
security_review: required
security_review_reason: builds an auto-merge path that closes a task without human review — the single highest-stakes mechanism in the phase. It must be provably OFF by default (empty policy → nothing auto-merges) and fire only on an explicit class enable AND a met track-record threshold. A default-on bug, an over-counted "clean merge", or a hook that fires before the enable check would ship unreviewed work.
docs_sync: required
docs_sync_reason: introduces a zero-review policy config and a new orchestrator behavior (even though disabled) plus `aet desk --eligibility`; the mechanism, its default-off guarantee, and the enablement path must be documented.
status: approved
---

# Plan: Zero-Review Mechanism — Track-Record Reader + Auto-Merge Hook (OFF by Default)

## Context

- PRD: `docs/prds/roadmap-p4-two-human-ends-prd.md` (G3; R-8, R-9). Builds the dark-exit-door mechanism and **ships it shut**. Enabling class #1 is explicitly **Phase 7's** exit gate on Phase 7's proof data — Phase 4 must not enable any class.
- **Ground truth (re-grounded 2026-07-15):** a **clean merge** = a task that reached `merged` (terminal) with every required stage verdict `pass`, no failed stage record, and no rework (no re-entry from `failed`, no repeated stage run). Sources: telemetry archive (`~/.aet/telemetry/...`) and `.agents/work-history.jsonl`. The orchestrator's `awaiting_merge` promote — the point it would otherwise leave the task for the human — is the **success path around `aet-work/bin/orchestrator:1761–1772`** (re-grounded; the PRD's original `:1517–1553` citation drifted during P3). Terminal transitions: `aet_queue.py` `awaiting_merge → {merged, abandoned}` (`:282`); `merged` is written only by `aet-state record-merge`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **Track-record reader** (`aet-work/lib/track_record.py`): computes, per `work_class`, the clean-merge count from the telemetry archive + history log, per the clean-merge definition above. Surfaced read-only as `aet desk --eligibility`, reporting each class's clean-merge count and whether that class is currently zero-review-enabled.
- **Zero-review policy**: a config naming the enabled classes and the per-class clean-merge threshold. **Empty by default** — nothing auto-merges. (Exact location — `.agents/aet-work.json` vs. a dedicated `.agents/review-policy.json` — is this plan's implementation choice per PRD Open Question 1; default stays empty/off.)
- **Orchestrator hook**: at the `awaiting_merge` promote (`orchestrator:~1761`), if — and only if — the task's `work_class` is explicitly enabled **and** its class track record meets the threshold, auto-transition `awaiting_merge → merged` through the **same** merge + `record-merge` closure path as twe-03 (no second closure writer). Otherwise leave the task for the human at the desk.
- `unclassified` is never eligible (twe-01 fail-safe). The shipped default config satisfies "the zero-review mechanism exists and is off."

## Rejected Alternatives

- **Enable a low-risk class (e.g. `trivial`) in this phase** — rejected: enablement is Phase 7's exit gate on scoreboard data; Phase 4 ships the mechanism OFF by explicit decision (dark factory from the exit door inward).
- **Count any `merged` task as a clean merge** — rejected: a merge that required rework or had a failed stage is not evidence of a trustworthy class; the definition demands all-pass, no-fail, no-rework so the track record means what it claims.
- **A new auto-merge closure writer in the orchestrator** — rejected: Non-Goals — auto-merge drives the existing `record-merge` path exactly like the human `desk merge`, keeping `merged` single-writer.

## Task List

1. Write `aet-work/lib/track_record.py`: per-class clean-merge computation from telemetry archive + history log — M (traces: R-8)
2. Add `aet desk --eligibility`: read-only per-class clean-merge count + enabled/disabled status — S (traces: R-8)
3. Add the zero-review policy loader (empty/off default) and the orchestrator auto-merge hook at the `awaiting_merge` promote, gated on enabled-class AND met-threshold, driving the `record-merge` closure path — M (traces: R-9)
4. Tests: `tests/test_zero_review.py` (new) — M (traces: R-8, R-9, R-11)
5. Merge branch to main and verify integration — S [Deferred: runs at `aet-ship`]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with twe-03 — both drive the closure path but from different callers (human desk vs. orchestrator hook) with different guards; distinct risk surfaces

## Files to Modify

- `aet-work/lib/track_record.py` (new)
- `aet-work/bin/desk`
- `aet-work/bin/orchestrator`
- `aet-work/lib/*` policy loader (location per Open Question 1)
- `tests/test_zero_review.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_zero_review.py`:
  - `test_clean_merge_counts_all_pass_no_rework`
  - `test_reworked_or_failed_merge_not_counted_clean`
  - `test_eligibility_reports_count_and_disabled_status`
  - `test_default_policy_empty_nothing_auto_merges`
  - `test_unclassified_never_eligible`
  - `test_enabled_class_at_threshold_auto_merges_via_closure_path`
  - `test_enabled_class_below_threshold_left_for_human`
- [ ] R-trace coverage: R-8 by tasks 1–2; R-9 by task 3; R-11 (this slice) by task 4; no unknown R-ids cited
- [ ] **Default-off assertion:** a full orchestrator run with the shipped default config auto-merges nothing (explicit test)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Since the mechanism ships OFF (empty policy), rollback removes dormant code — no behavior was active to unwind. The track-record reader is read-only.

## Pipeline

`pipeline: standard` with `security_review: required` — the highest-stakes path in the phase; review focuses on the default-off guarantee and the enabled-AND-qualified gate.

---

*Stage: secure*
*Next step: run `aet-sync-docs`, then `aet-ship`*

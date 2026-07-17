---
id: nsr-02-quarantined-state
size: M
blocked_by:
  - twe-07-exit-gate-rehearsal
pipeline: standard
status: approved
security_review: skipped
security_review_reason: adds one terminal-until-human state to the transition table; all writes still route through `aet-state` (sole-writer preserved). No new writer, network, or trust boundary. Fail-safe — the state is non-actionable, so a mis-set never causes autonomous action.
docs_sync: required
docs_sync_reason: `quarantined` is a user-facing task state — `docs/PIPELINE.md` Legal Transitions, the CONTEXT.md state glossary, and the panel's state rendering all change; operators need to know what a quarantined task means and how to un-quarantine it.
---

# Plan: `quarantined` Task State (state machine, wired but inert)

## Context

- PRD: `docs/prds/roadmap-p5-night-shift-runtime-prd.md` (G2; R-3). Records ADR-030's state-machine half (authored in `aet-validate-scope`).
- The breaker (nsr-03) is what *drives* tasks into `quarantined`; this plan only adds the state and makes it legal, non-actionable, and rendered. Shipped inert — nothing sets it yet, so behavior is unchanged until nsr-03.
- **Ground truth (2026-07-15):** states live in `LEGAL_TRANSITIONS` (`aet-work/lib/aet_queue.py:274`): `planned/blocked/ready/in_progress/awaiting_merge/merged/abandoned/failed`. `failed` is retry-eligible (`failed → {in_progress, ready, blocked, abandoned}`), so it cannot express "do not retry"; `abandoned` is human-terminal. `quarantined` is the missing "deterministic failure, out of the retry loop until a human acts." Transition validation + derived-state reconciliation live in `aet-work/bin/aet-state`; the spawn selector is `has_actionable_tasks` / the `run_batch` picker (`aet-work/bin/orchestrator`).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- Add `quarantined` to `LEGAL_TRANSITIONS`: `in_progress → quarantined`, `failed → quarantined`, and `quarantined → {ready, abandoned}` (a human un-quarantines after a fix, or abandons). No other source or target.
- `aet-state` learns the state in its transition-validation and derived-state reconciliation paths; `quarantined` reconciles to itself (never auto-derived away).
- `quarantined` is **non-actionable**: `has_actionable_tasks` and the `run_batch` spawn selector exclude it, exactly as they exclude `merged`/`abandoned`, so the breaker's decision is enforced by the state machine (ADR-011 determinism), not by orchestrator memory.
- Panel renders the new state (label + color) so a quarantined task is legible in the live view.
- Docs: `docs/PIPELINE.md` Legal-Transitions table gains `quarantined` and the un-quarantine path (the CONTEXT.md glossary already defines `quarantined` and the five failure terms — added at scope-validation, 2026-07-16).

## Rejected Alternatives

- **Reuse `failed` + a `quarantine: true` flag** — rejected: `failed → in_progress/ready` is legal, so a flagged-failed task remains selectable and could be re-spawned; correctness would depend on every picker honoring the flag. A distinct non-actionable state makes "do not retry" a property of the state machine, not a convention.
- **Reuse `abandoned`** — rejected: `abandoned` means a human deliberately dropped the task; conflating a breaker quarantine with human abandonment loses the "needs a fix, then re-enter" semantics and the distinct un-quarantine path.
- **Make `quarantined` fully terminal (no exits)** — rejected: a quarantine must be recoverable after the underlying fix; `quarantined → ready` is the explicit human re-entry, `→ abandoned` the give-up.

## Task List

1. ✓ Add `quarantined` and its transitions to `LEGAL_TRANSITIONS` (`aet-work/lib/aet_queue.py`) — S (traces: R-3)
2. ✓ Teach `aet-state` transition-validation + derived-state reconciliation about `quarantined` (self-reconciling) — S (traces: R-3)
3. ✓ Exclude `quarantined` from `has_actionable_tasks` and the `run_batch` spawn selector — S (traces: R-3)
4. ✓ Render `quarantined` in the panel state view — S (traces: R-3)
5. ✓ Docs: `docs/PIPELINE.md` Legal Transitions gains `quarantined` and the un-quarantine path (CONTEXT.md glossary already carries it from scope-validation) — S (traces: R-3)
6. ✓ Tests: `tests/test_quarantined_state.py` (new) — M (traces: R-3, R-13)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch — nsr-03 drives this state and is `blocked_by` it; the state must exist and be legal first

## Files to Modify

- `aet-work/lib/aet_queue.py`
- `aet-work/bin/aet-state`
- `aet-work/bin/orchestrator` (spawn selector / `has_actionable_tasks`)
- `aet-work/panel/` (state rendering)
- `docs/PIPELINE.md`
- `tests/test_quarantined_state.py` (new)

## Validation Steps

- [x] `make validate` passes; full suite passes
- [x] New source coverage — `tests/test_quarantined_state.py`:
  - `test_quarantined_legal_targets` (`in_progress`/`failed` → `quarantined`)
  - `test_quarantined_legal_sources` (`quarantined` → `ready`/`abandoned` only)
  - `test_quarantined_to_in_progress_rejected`
  - `test_quarantined_not_actionable` (spawn selector never picks it)
- [x] R-trace coverage: R-3 by tasks 1–5; R-13 (this slice) by task 6; no unknown R-ids
- [x] Distinguish test types: unit (transition table) + integration (`aet-state` end-to-end transition)
- [x] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The state is additive and unset by any code until nsr-03; absent it, the state machine behaves exactly as today.

## Pipeline

`pipeline: standard` — state-machine change with docs sync; the `aet-state` transition path is the integration surface, adequately covered by `standard` grouping.

---

*Stage: synced*
*Next step: run `aet-ship`*

---
id: nsr-04-on-failure-triage
size: M
blocked_by:
  - nsr-01-failure-taxonomy-signature
  - nsr-02-quarantined-state
  - nsr-03-circuit-breaker
pipeline: standard
status: approved
security_review: required
security_review_reason: introduces a new autonomous agent session (triage) that runs unattended and can requeue work; the triage prompt and its verdict parsing are load-bearing. Review confirms it fails closed (an errored/unparseable triage falls back to the deterministic classifier and stays breaker-bounded, never an unbounded retry loop) and that it never merges or grants work.
docs_sync: required
docs_sync_reason: `--on-failure={triage|continue|halt}` is a new operator-facing flag and this is where the failure taxonomy first becomes observable — the five classes and the three modes are documented in `docs/PIPELINE.md` / `docs/CONVENTIONS.md` and the `aet run` help.
---

# Plan: `--on-failure=triage` — Triage Session + Requeue Path (default: triage)

## Context

- PRD: `docs/prds/roadmap-p5-night-shift-runtime-prd.md` (G1; R-7, R-8).
- The behavioral capstone of the failure chain: consumes nsr-01 (class + signature), nsr-02 (`quarantined`), and nsr-03 (breaker verdict). Turns "a failed task waits until morning" into "classify → requeue or quarantine → shift continues."
- **Ground truth (2026-07-15):** `aet run` today has no `--on-failure` flag; a failure is `_mark_failed` → `failed` and the loop continues (`run_batch`, `aet-work/bin/orchestrator:1249`). Sessions are spawned via `run_stage`/`_spawn_session` (`:567`) with a prompt from `build_prompt` (`:285`); this is the machinery the triage session reuses. `--on-failure=continue` reproduces exactly today's behavior.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `aet run` gains `--on-failure={triage|continue|halt}`, default **`triage`**.
- On a task failure the finalize path: (1) classifies via nsr-01 and computes the signature; (2) consults nsr-03 — a breaker hit ⇒ `→ quarantined`, done; (3) otherwise, by mode:
  - **`triage`**: spawn a cheap triage session (active adapter; a reserved `triage` routing key exists but routing to a cheaper harness is Phase 6/7 — Non-Goal). The session receives the failure tail + stage + the nsr-01 class as prior and emits a structured verdict `{class, action: requeue|quarantine}`. `requeue` ⇒ `failed → ready` (R-8, via `aet-state`, sole-writer preserved); `quarantine` ⇒ `→ quarantined`. **Fail-closed:** an errored or unparseable triage falls back to the nsr-01 `classify()` default (`environment` ⇒ requeue), always bounded by the nsr-03 per-task breaker so requeue cannot loop past the threshold.
  - **`continue`**: today's behavior — `→ failed`, no triage session, shift continues.
  - **`halt`**: stop the shift on first failure (set `stop_spawn`, drain, exit non-zero).
- New `aet-work/lib/triage.py` holds the triage prompt builder and the verdict parser (pure, testable); the orchestrator owns spawning and the state transition.

## Rejected Alternatives

- **Requeue without a breaker cap** — rejected: a genuinely broken task would requeue forever, burning the whole shift. The nsr-03 per-task threshold is the required cap; triage routes, the breaker bounds.
- **Trust the triage session's class over the deterministic signature for breaker counting** — rejected: the breaker key must stay deterministic (nsr-01) so identical failures always collide; the session decides *action*, not the counting key.
- **Make `continue` the default** — rejected: the phase's entire purpose is an unattended shift that survives failures; `triage` default is the night-shift default (owner decision), with `continue`/`halt` as explicit opt-outs.

## Task List

1. Add `--on-failure={triage|continue|halt}` (default `triage`) to the orchestrator parser and thread it into `run_batch` — S (traces: R-7)
2. Create `aet-work/lib/triage.py`: triage prompt builder + structured-verdict parser (pure) — M (traces: R-7)
3. Wire the finalize path: classify → breaker → mode routing; `triage` spawns the session and requeues/quarantines, fail-closed to the nsr-01 default — M (traces: R-7, R-8)
4. Docs: document the five failure classes and the three `--on-failure` modes in `docs/PIPELINE.md` / `docs/CONVENTIONS.md` and `aet run` help — S (traces: R-7)
5. Tests: `tests/test_on_failure_triage.py` (new) — M (traces: R-7, R-8, R-13)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch — depends on three prior plans; distinct behavioral surface (session spawning + requeue)

## Files to Modify

- `aet-work/bin/orchestrator` (parser + finalize routing + triage spawn)
- `aet-work/lib/triage.py` (new)
- `docs/PIPELINE.md`, `docs/CONVENTIONS.md`
- `tests/test_on_failure_triage.py` (new)

## Validation Steps

- [x] `make validate` passes; full suite passes
- [x] New source coverage — `tests/test_on_failure_triage.py` covers `aet-work/lib/triage.py` + the routing:
  - `test_triage_requeues_flaky_environment` (`failed → ready`)
  - `test_triage_quarantines_design`
  - `test_triage_error_falls_back_to_classifier_default` (fail-closed)
  - `test_triage_requeue_bounded_by_breaker` (no loop past threshold)
  - `test_on_failure_continue_matches_legacy` / `test_on_failure_halt_stops_shift`
- [x] R-trace coverage: R-7 by tasks 1–4; R-8 by task 3; R-13 by task 5; no unknown R-ids
- [x] Distinguish test types: unit (`triage.py` prompt/parse) + integration (finalize routing + `aet-state` requeue)
- [x] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The `--on-failure` default disappears and failures fall back to the nsr-03/nsr-02 terminal behavior; no persisted state depends on this plan.

## Pipeline

`pipeline: standard` — spawns a new session type and mutates state on the failure path; `standard` grouping plus the required security review cover the autonomy surface.

---

*Stage: secure*
*Next step: run `aet-sync-docs`, then `aet-ship`*

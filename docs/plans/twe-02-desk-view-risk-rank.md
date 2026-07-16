---
id: twe-02-desk-view-risk-rank
size: M
blocked_by:
  - twe-01-work-class-attribute
pipeline: standard
security_review: skipped
security_review_reason: read-only projection — lists `awaiting_merge` tasks and reads existing verdict files; writes nothing, mutates no state, opens no network. The risk score is a pure function of already-recorded local signals.
docs_sync: required
docs_sync_reason: new user-facing `aet desk` subcommand (and its `--json` projection); the dispatcher's subcommand set and user docs gain a row.
status: approved
---

# Plan: `aet desk` — Risk-Ranked `awaiting_merge` View + Evidence Bundle

## Context

- PRD: `docs/prds/roadmap-p4-two-human-ends-prd.md` (G1; R-1, R-2; the `--json` slice of R-1).
- This plan is the **read** half of the desk; actions (`merge`/`abandon`) are twe-03. It surfaces every task the human must decide on, riskiest first, with the evidence needed to decide, so scarce review minutes go to the riskiest work first.
- **Ground truth (re-grounded 2026-07-15):** `awaiting_merge` is the "awaiting review" state (`aet-work/lib/aet_queue.py` `LEGAL_TRANSITIONS:274`, `in_progress → awaiting_merge → merged` at `:281–282`). The evidence bundle is read via `evidence.evidence_path(task_id, kind)` (`aet-work/lib/evidence.py:84`) → `~/.aet/reports/{slug}/{task_id}/{kind}.json`; `SCHEMAS` (`:21`) for `qa`/`review`/`cso`/`sync-docs` carry `verdict`, `summary`, `findings`/`divergences`, and (qa) `tests_total`/`tests_passed`/`tests_failed`. Risk signals also come from `telemetry.stage_record` (`files_modified`) and `test_run_record` (`tests_failed`), plus plan `size`/`work_class` via `plan_parser.parse_frontmatter`.
- **Dispatch shape (re-grounded):** two-word/subcommand dispatch is settled by `aet gate submit` (ewl-01) — a `gate` exec row in `aet-work/bin/aet` `SUBCOMMANDS` (`:29`) targeting `aet-work/bin/gate`, which uses an argparse subparser. `aet desk` follows: a one-row `"desk": {"target": ("aet-work", "desk"), "mode": "exec"}` addition + a new `aet-work/bin/desk`. Target passes the **bare** bin name (`_resolve_target` composes `bin/`).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- New `aet-work/bin/desk` (stdlib-only). Default action lists exactly the `awaiting_merge` tasks; for each it attaches the evidence bundle (the four verdicts' pass/fail, summary, findings count, test totals), and **flags any required-but-missing verdict as a visible gap** — never silently omitted.
- **Deterministic risk score** in a pure, unit-tested function (`lib/risk.py` or a `desk`-local pure fn): a weighted sum over already-available signals — `work_class` (`critical` > `normal` > `trivial`; `unclassified` ranks *elevated*), plan `size` (L > M > S), review/cso findings counts, any `fail` or missing required verdict, `files_modified` count, and `tests_failed > 0`. Weights are data (a module-level table), tunable later without changing the contract. The desk prints the contributing factors per task so ranking is legible, not opaque.
- `--json` emits a machine-readable projection mirroring `status --json`, for the future read-only surface and any machine consumer.

## Rejected Alternatives

- **LLM/heuristic risk ranking** — rejected: ADR-020 (determinism over discretion). Ranking must be a pure, inspectable function of recorded signals, reproducible across runs on the same inputs.
- **Compute risk inside the `--json` path and re-derive for the human view** — rejected: one scoring function feeds both the human table and the JSON, so the printed factors and the JSON fields can never disagree.
- **Rank `unclassified` as lowest risk** — rejected: unknown risk needs eyes, not a free pass; `unclassified` ranks elevated so unlabeled work surfaces near the top.

## Task List

1. ✓ Write the pure risk-scoring function (weighted signal table, legible per-factor breakdown) with stable ordering — M (traces: R-2)
2. ✓ Write `aet-work/bin/desk`: `awaiting_merge` filter, evidence-bundle attachment with missing-verdict gap flagging, risk-ordered human table, `--json` projection — M (traces: R-1, R-2)
3. ✓ Add the `desk` row to `aet-work/bin/aet` `SUBCOMMANDS` — S (traces: R-1)
4. ✓ Tests: `tests/test_desk_view.py` (new) — M [Changed: also updated `tests/test_aet_dispatcher.py` to cover the new `desk` row in the dispatcher spec table] (traces: R-1, R-2, R-11)
5. Merge branch to main and verify integration — S [Deferred: runs at `aet-ship`]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with twe-03 — actions build on this view and are `blocked_by` it; keeping read and write in separate plans keeps the read surface non-mutating

## Files to Modify

- `aet-work/bin/desk` (new)
- `aet-work/lib/risk.py` (new)
- `aet-work/bin/aet`
- `tests/test_desk_view.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_desk_view.py`:
  - `test_desk_lists_only_awaiting_merge`
  - `test_evidence_bundle_attached_per_task`
  - `test_missing_required_verdict_shown_as_gap`
  - `test_risk_order_stable_across_runs`
  - `test_critical_outranks_trivial`
  - `test_unclassified_ranks_elevated`
  - `test_json_projection_matches_human_view`
  - `test_desk_routed_through_aet_dispatcher` (subprocess: `aet desk` reaches `bin/desk`)
- [ ] R-trace coverage: R-1 by tasks 2–3; R-2 by tasks 1–2; R-11 (this slice) by task 4; no unknown R-ids cited
- [ ] Skill/dispatch check: `aet desk --json` parses as valid JSON in a subprocess smoke case
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The desk is read-only, so removal restores the prior review workflow (reading verdict files by hand / `status`) with no state to unwind.

## Pipeline

`pipeline: standard` — a new read-only command; no per-stage isolation profile needed.

---

*Stage: synced*
*Next step: run `aet-ship`*

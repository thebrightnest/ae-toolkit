---
id: ewl-01-gate-submit-cli
size: M
blocked_by:
  - cli-03-skills-lint
  - frh-18-group-evidence-path-contract
  - uct-01-usage-cost-telemetry
pipeline: standard
security_review: required
security_review_reason: new CLI writer for gate verdicts that the orchestrator's fail-closed gate (frh-11) trusts for pass/fail decisions — validation-bypass or injection here would defeat the evidence gate itself
docs_sync: required
docs_sync_reason: new user-facing aet subcommand, and the four checking skills' writer contract changes from a direct library call to this command
---

# Plan: `aet gate submit` — Centralized, Fail-Closed Verdict Writer

## Context

- PRD: `docs/prds/roadmap-p3-enforcement-walls-prd.md` (G1; R-1, R-2, plus R-8 tests)
- **Mode-neutral by construction (contributes to G5 for free):** `aet gate submit` delegates to `evidence.write_verdict`, which already writes to the external report store `~/.aet/reports/{slug}/` (ADR-019), not the tracked tree — so verdict submission adds nothing to a Mode-1 project's repo footprint. No change is needed here for the non-invasive scope; this note records that it was checked, not skipped.
- frh-10 built the evidence layer (`aet-work/lib/evidence.py`: `write_verdict`, `validate_verdict`, `SCHEMAS` for `qa`/`review`/`cso`/`sync-docs`) and frh-11 made the orchestrator's gate fail-closed on missing/invalid verdicts. Today the four checking skills (`aet-qa`, `aet-review`, `aet-cso`, `aet-sync-docs`) write verdicts by importing `evidence.py` directly from skill prose ("Use `aet-work/lib/evidence.py` (`write_verdict`) when available; otherwise write equivalent JSON") — there is no CLI entry point, and no argument-level validation before `write_verdict` is called.
- cli-01 (`aet-work/bin/aet`, `awaiting_merge`) built the multicall dispatcher with a `SUBCOMMANDS` spec table explicitly designed so "Phase 3+ subcommands are one-row additions." This plan adds that row.
- **Dependency on frh-18 (`status: approved`, queued `ready`)**: found during Phase 3 clarify-goal grounding to target the exact same `run_stage`/`run_stage_group` root cause originally scoped here as a separate `ewl-02` plan — frh-18 is the more correct fix (per-kind `AET_EVIDENCE_PATH_<KIND>` precedence, handling concurrent multi-stage group sessions correctly) and is already queued, so `ewl-02` was abandoned in its favor (see the sizing note in `docs/prds/roadmap-p3-enforcement-walls-prd.md`; the ewl-02 plan file was deleted 2026-07-12 after abandonment). `aet gate submit`'s delegation to `evidence.write_verdict` should resolve its destination path through frh-18's canonical `resolve_verdict_path()`, not the pre-fix ambiguous default — hence `blocked_by: frh-18-group-evidence-path-contract`. frh-18 also rewrites the same four checking skills' writer-contract paragraph (to its three-step precedence prose) that task 3 below rewrites again (to `aet gate submit`); this is sequential evolution of one paragraph, not a conflicting edit — ewl-01 always lands after frh-18 by the blocked_by edge, so it supersedes whatever frh-18 left there.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- New `aet-work/bin/gate` (stdlib-only Python): `gate submit --stage <s> --verdict pass|fail --evidence <path>`. Resolves `<s>` against `evidence.SCHEMAS` keys; reads `--evidence` as a JSON file; calls `evidence.validate_verdict` before `evidence.write_verdict`. Any failure (missing arg, unreadable file, schema-invalid payload) prints a named error to stderr and exits 1 — never a silent or partial write.
- `aet`'s `SUBCOMMANDS` table gains `"gate": {"target": ("aet-work", "gate"), "mode": "exec"}` — same exec-dispatch pattern as every other row (cli-01 precedent); no argument re-parsing in `aet` itself. Note the target passes the **bare** bin-name `"gate"`, not `"bin/gate"`: `_resolve_target` already composes `_skills_root()/skill_dir/"bin"/bin_name` (`aet-work/bin/aet:104`), so a `bin/`-prefixed value would resolve to `aet-work/bin/bin/gate`.
- Writer contract in the four checking skills changes from "use `evidence.py` (`write_verdict`) directly" to "run `aet gate submit --stage <stage> --verdict <verdict> --evidence <path>`" — the CLI becomes the sole sanctioned writer, matching the PRD's G1.

## Rejected Alternatives

- **Skip CLI-level validation and let `evidence.write_verdict` raise on bad input** — rejected: exceptions from a library call produce a traceback, not a clean fail-closed exit; a dedicated CLI layer gives predictable exit codes and named errors that skills (and the future pre-push hook, ewl-03) can rely on.
- **Fold this into cli-02's `build_parser()` sweep** — rejected: that plan is a mechanical, behavior-preserving refactor of existing bins; `gate` is new capability and belongs to the phase that owns it.

## Task List

1. Write `aet-work/bin/gate`: `submit` subcommand, argument validation, delegation to `evidence.validate_verdict`/`write_verdict`, named errors on every failure path — M (traces: R-1, R-2)
2. Add the `gate` row to `aet-work/bin/aet`'s `SUBCOMMANDS` table — S (traces: R-1)
3. Update the writer contract in `aet-qa/SKILL.md`, `aet-review/SKILL.md`, `aet-cso/SKILL.md`, `aet-sync-docs/SKILL.md`: replace the direct `write_verdict` import instruction with `aet gate submit`. Batched deliberately — four near-identical one-paragraph edits to the same contract, same reasoning cli-02 used for its twelve-bin `build_parser()` sweep — S (traces: R-1)
4. Tests: `tests/test_gate_submit.py` (new) — M (traces: R-1, R-2, R-8)
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level (the four SKILL.md edits are batched _within_ this plan for the same reason cli-02 batched twelve bins — see task 3)
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with frh-18 (this plan's own dependency, not batching) or ewl-03/04/05 (distinct files, distinct risk surface)

## Files to Modify

- `aet-work/bin/gate` (new)
- `aet-work/bin/aet`
- `aet-qa/SKILL.md`
- `aet-review/SKILL.md`
- `aet-cso/SKILL.md`
- `aet-sync-docs/SKILL.md`
- `tests/test_gate_submit.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_gate_submit.py` (unit + one subprocess integration case):
  - `test_submit_writes_valid_verdict`
  - `test_missing_verdict_flag_exits_nonzero`
  - `test_missing_evidence_flag_exits_nonzero`
  - `test_evidence_file_not_found_exits_nonzero`
  - `test_schema_invalid_payload_exits_nonzero`
  - `test_unknown_stage_exits_nonzero`
  - `test_gate_submit_routed_through_aet_dispatcher` (subprocess: `aet gate submit ...` reaches `bin/gate`)
- [ ] R-trace coverage: R-1 by tasks 1–3; R-2 by task 1; R-8 by task 4; no unknown R-ids cited
- [ ] Skill-structure check: `./scripts/validate-skills.sh` passes with the four SKILL.md edits
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The four skills' fallback instruction ("otherwise write equivalent JSON") still applies if `aet gate submit` is unavailable; frh-11's schema-invalid-verdict fail-closed gate covers the fallback path regardless.

## Pipeline

`pipeline: standard` — TDD→implement→QA, review, CSO grouping is appropriate; this plan introduces a new trusted writer, not a risk profile that needs full per-stage isolation.

---

_Stage: reviewed_
_Next step: run `aet-cso`_

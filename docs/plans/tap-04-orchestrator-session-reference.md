---
id: tap-04-orchestrator-session-reference
size: M
blocked_by: [tap-03-adapter-dispatched-session-readers]
pipeline: standard
status: queued
security_review: skipped
security_review_reason: replaces one resolved local path with an adapter-resolved reference to the same class of file and adds an existing session identifier to a local telemetry record; no new external input, no credential or network surface, and the identifier is the agent CLI's own session id, not user-supplied
docs_sync: required
docs_sync_reason: the telemetry stage-record schema gains a field and `session_dir` retires as a cross-adapter concept; docs/telemetry-guide.md and CONTEXT.md's Session Log term must reflect the traceability contract
---

# Plan: Adapter-Resolved Session Reference and Traceable Stage Records

## Context

- PRD: `docs/prds/telemetry-adapter-parity-prd.md` (R-6, R-9)
- ADR: `docs/adr/050-session-log-extraction-per-adapter.md` (decisions 2 and 4)
- Measured motivation: `reports/2026-07-25-aet-performance-observability-review.md` — 74 groups
  hold a claimed `test_run` record with no observed twin, and none of them can be explained
  because no telemetry record persists a session identifier.
- Verified current behaviour (2026-07-26):
  `_spawn_session_with_tail` (`src/aet/cli/orchestrator.py:882`) sets
  `session_dir = None` and overwrites it only `if adapter.name == "kimi"` (`:901-903`).
  `_emit_wire_test_runs` (`:603`) opens with `if session_dir is None: return` (`:615`), so a
  non-kimi CLI emits **zero** observed `test_run` records by construction.
  `telemetry.stage_record` (`src/aet/telemetry.py:192`) has no session-identifier parameter.
- `usage_lib.resolve_kimi_session_dir_from_output` scrapes a resume hint from captured stdout —
  a kimi-specific route. Claude's result envelope carries `session_id` directly, and every
  transcript record carries `cwd`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
  — the kimi gate is a defect in effect, but the deliverable is an adapter-resolved reference
  plus a telemetry schema field, which a targeted fix cannot produce.

## Locked design

- **The adapter resolves its own session reference** from the captured session output
  (ADR-050 decision 2). The orchestrator asks; it does not branch on `adapter.name`. The
  `session_dir` name and the kimi-shaped `Path | None` contract retire together.
- **Claude resolves by `session_id` from the result envelope**, confirmed against the record's
  `cwd`, per the PRD's resolved question. A mismatch or an unparseable envelope resolves to
  `None` — never a guessed transcript. That null is also the R-11 failure mode, so the two
  surface the same way.
- **`_emit_wire_test_runs` keeps its best-effort contract**: a null reference emits nothing, and
  any extraction exception prints a warning and returns. Telemetry never blocks a run.
- **`stage_record` gains a session identifier** (R-9), populated from the resolved reference and
  `None` when it could not be resolved. It is an identifier plus enough to locate the log — not a
  copy of its contents.
- **Resolution is documented, not just stored.** `docs/telemetry-guide.md` states how to go from
  a stage record's session identifier to a session-log path for each CLI, so the traceability
  claim is verifiable by a human with the archive and nothing else.
- **Null-honest throughout** (ADR-031): an unresolvable session yields a null identifier and zero
  observed records, never a fabricated path or a partial guess.

## Rejected Alternatives

- **Keep `session_dir` and add a `claude` branch beside the `kimi` branch** — rejected
  (ADR-050): it hardcodes a second CLI name at the same site and makes a third adapter a third
  edit to the orchestrator.
- **Persist the full session-log path on the record** — rejected: paths are machine- and
  home-directory-specific and go stale; the identifier plus a documented resolution rule survives
  a moved archive.
- **Copy the session log into the telemetry archive** — rejected as scope and size; the CLI's own
  log is the source of truth and duplicating it invites the two to diverge.
- **Put the session identifier only on `test_run` records** — rejected: the orphan records that
  motivated R-9 are the ones with no observed twin, so the identifier must live on the record
  type that is always written — `stage`.

## Task List

1. Add session-reference resolution to the adapter layer (kimi: existing resume-hint route;
   claude: `session_id` from the result envelope confirmed against `cwd`; unresolvable → `None`)
   — M (traces: R-6)
2. Replace the `adapter.name == "kimi"` gate in `_spawn_session_with_tail` with the
   adapter-resolved reference; rename `session_dir` through its call chain and update the
   docstrings that describe it as a kimi wire dir — S (traces: R-6)
3. Route `_emit_wire_test_runs` through the `tap-03` dispatch, preserving the best-effort and
   null-reference contracts — S (traces: R-6)
4. Add the session identifier to `telemetry.stage_record` and populate it at the emission site —
   S (traces: R-9)
5. Document the identifier → session-log resolution for both CLIs in `docs/telemetry-guide.md` —
   S (traces: R-9)
6. Tests (see Validation Steps) — M (traces: R-6, R-9)
7. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: R-6 and R-9 are one edit to one seam — the resolved reference is both what
  makes extraction adapter-neutral and what gets persisted for traceability. Splitting them would
  mean resolving a reference in one plan and storing it in the next.

## Files to Modify

- `src/aet/cli_adapter.py`
- `src/aet/cli/orchestrator.py`
- `src/aet/telemetry.py`
- `src/aet/usage.py` (kimi resume-hint resolver moves behind the adapter seam)
- `tests/cli/test_cli_adapter.py`
- `tests/orchestrator/test_orchestrator.py`
- `tests/telemetry/test_telemetry.py`
- `docs/telemetry-guide.md`

## Validation Steps

- [ ] `make validate` passes
- [ ] Coverage:
  - `test_session_reference_resolved_per_adapter_without_name_branch` (unit) — asserts no
    `adapter.name ==` comparison remains on the resolution path
  - `test_claude_session_reference_resolved_from_envelope_session_id` (unit)
  - `test_claude_session_reference_null_when_cwd_mismatches` (unit)
  - `test_claude_session_reference_null_when_envelope_unparseable` (unit)
  - `test_kimi_session_reference_unchanged` (unit) — regression contract
  - `test_emit_test_runs_noop_on_null_session_reference` (unit)
  - `test_emit_test_runs_survives_extraction_exception` (unit)
  - `test_stage_record_carries_session_identifier` (unit)
  - `test_stage_record_session_identifier_null_when_unresolvable` (unit)
- [ ] R-trace coverage: R-6 by tasks 1, 2, 3, 6; R-9 by tasks 4, 5, 6; no unknown R-ids
- [ ] For the new resolution logic in `cli_adapter.py`, tests above name the coverage
- [ ] End-to-end: an orchestrated stage session run under `claude` writes at least one `test_run`
      record with a non-null `duration_seconds`, and its `stage` record carries a session
      identifier that resolves to the transcript that produced it
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; the kimi-only gate returns and Claude sessions stop emitting observed
records. Stage records written under this change carry an extra field that a reverted reader
ignores — the telemetry schema is additive and readers tolerate unknown keys — so archived
records stay readable either way.

---

*Stage: tdd-complete*
*Next step: run `aet-implement`*

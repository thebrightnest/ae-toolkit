---
id: ttf-01-wire-test-run-extraction
size: M
blocked_by: []
pipeline: standard
status: approved
security_review: skipped
security_review_reason: passive parser of local session logs; commands are recorded into telemetry, never executed; no network, no secrets, no new trust boundary
docs_sync: required
docs_sync_reason: telemetry-log-schema.md must document wire-derived test_run records, the scope vocabulary, and the duration null contract
---

# Plan: Wire-Log Test-Run Extraction

## Context

- PRD: `docs/prds/test-telemetry-fidelity-prd.md` (R-1, R-2, R-3).
- Today a kimi session's test activity is invisible to telemetry: the only
  `test_run` records come from the QA verdict gate (one per task, fabricated
  scope/duration). The session wire log
  (`~/.kimi-code/sessions/<wdKey>/<sessionId>/agents/*/wire.jsonl`) already
  records every `tool.call`/`tool.result` pair with top-level `time`
  (verified 2026-07-13: lvp-01 session — 4 test invocations, pairable
  timestamps). `usage.py:_resolve_kimi_session_dir` already maps a session id
  to its wire dir after exit.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **New module `aet-work/lib/wirelog.py`.**
  - `extract_test_invocations(session_dir: Path) -> list[dict]`: walk
    `agents/*/wire.jsonl`; for each `context.append_loop_event` whose event is
    `tool.call` with `name == "Bash"`, match `args.command` against the test
    runner patterns; pair with the `tool.result` event sharing
    `uuid`/`parentUuid`; emit `{command, start_time, end_time,
duration_seconds, exit_code}` from the records' top-level `time`.
  - Defensive by contract (mirrors `usage.py`): skip lines >
    `_MAX_WIRE_LINE_CHARS`, malformed JSON, missing pairs, missing `time`;
    unpaired calls produce `duration_seconds: None` — never estimates.
  - Test-runner match list (v1): `pytest`, `python -m pytest`,
    `python3 -m pytest`, `vitest`, `jest`, `make test`, `make validate`,
    `npm test`, `cargo test`, `go test`.
- **Shared classifier in `aet-work/lib/telemetry.py`.**
  `classify_test_scope(command: str) -> str`: command names specific test
  files/dirs → `impact`; bare suite runners → `full-suite`; matched but
  unrecognized shape → `unknown`. This is the single scope heuristic for all
  emission sites (ttf-02 consumes it too).
- **`test_run_record` null contract.** `start_time`/`end_time` become
  optional; `duration_seconds` is `None` when either is missing (currently
  always computed from two required timestamps).
- **Orchestrator emission.** After a kimi session exits,
  `_emit_stage_session` resolves the session dir (reuse the resume-hint
  parsing already done for usage — extend the shared path, don't fork it) and
  appends one `test_run` record per extracted invocation, tagged with the
  session's `stage`. Non-kimi CLIs and unresolvable sessions emit nothing.
- **Schema doc.** `telemetry-log-schema.md` gains: wire-derived `test_run`
  provenance, the `full-suite`/`impact`/`unknown` vocabulary, and the
  duration/timestamp null contract.

## Rejected Alternatives

- **Require agents to self-report test runs into the verdict/telemetry** —
  rejected: depends on prompt compliance, varies by CLI, and the data already
  exists passively in the wire log.
- **Extend `usage.py` with the extraction instead of a new module** —
  rejected: usage.py is scoped to token/cost parsing; mixing concerns makes
  both harder to re-verify on kimi upgrades. Shared helpers
  (`_resolve_kimi_session_dir`, line cap) are imported.
- **Parse claude session logs in the same pass** — rejected: different format,
  separate investigation; explicitly out of PRD scope.
- **Classify scope with an LLM or path-existence checks** — rejected:
  non-deterministic or environment-dependent; a command-string heuristic is
  auditable and stable.

## Task List

1. `aet-work/lib/wirelog.py`: extraction + pairing + defensive parsing — M
   (traces: R-1, R-3)
2. `tests/test_wirelog.py` (new): fixture wire.jsonl covering paired calls,
   unpaired call (null duration), non-test commands ignored, malformed line
   skipped, multi-agent dirs — M (traces: R-1, R-3)
3. `telemetry.py`: `classify_test_scope` + nullable timestamps in
   `test_run_record`; extend `tests/test_telemetry.py` — S (traces: R-2, R-3)
4. `orchestrator`: emit per-invocation `test_run` records after kimi sessions
   in `_emit_stage_session`; integration test in
   `tests/test_orchestrator.py` asserting N records with real durations from
   a fixture session — M (traces: R-1, R-2)
5. Docs: `telemetry-log-schema.md` provenance + scope vocabulary + null
   contract — S (traces: R-3)
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks.

## Files to Modify

- `aet-work/lib/wirelog.py` (new — covered by `tests/test_wirelog.py`)
- `aet-work/lib/telemetry.py`
- `aet-work/bin/orchestrator`
- `tests/test_wirelog.py` (new)
- `tests/test_telemetry.py`
- `tests/test_orchestrator.py`
- `aet-work/references/telemetry-log-schema.md`

## Validation Steps

- [x] Lint passes (`make lint-py`)
- [x] Tests pass (`python3 -m pytest tests/test_wirelog.py tests/test_telemetry.py tests/test_orchestrator.py -q`, then full suite before commit)
- [x] Unit: `tests/test_wirelog.py` covers `aet-work/lib/wirelog.py` (paired, unpaired, malformed, non-test, multi-agent)
- [x] Integration: orchestrator test proves a fixture kimi session yields one `test_run` per invocation with classified scope and measured duration
- [x] R-trace coverage: R-1, R-2, R-3 all covered; no unknown R-ids cited
- [x] Live check: run one queued plan under `aet run` (or replay a recent session dir) and confirm real `test_run` records land in the task JSONL
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Wire extraction stops; the verdict-gate emission
path (pre-existing) keeps writing its records unchanged. No data mutation —
telemetry is append-only, so already-written real records stay valid.

## Pipeline

`standard` — new lib module plus orchestrator emission path; no
auth/data-model/API surface.

---

_Stage: reviewed_
_Next step: run `aet-sync-docs`_

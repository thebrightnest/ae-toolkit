---
id: tap-03-adapter-dispatched-session-readers
size: M
blocked_by: [tap-02-shared-runner-registry]
pipeline: standard
status: queued
security_review: required
security_review_reason: adds a reader for a new on-disk path family (~/.claude/projects/**) parsed with untrusted-content assumptions — line-length caps, JSON failure tolerance, and no path traversal outside the resolved project dir; the kimi reader's existing hardening must be matched, not re-derived
docs_sync: required
docs_sync_reason: ADR-050 defines the extension point; docs/telemetry-guide.md and CONTEXT.md's Session Log term must describe both readers
---

# Plan: Adapter-Dispatched Session-Log Readers (kimi + Claude Code)

## Context

- PRD: `docs/prds/telemetry-adapter-parity-prd.md` (R-4, R-5)
- ADR: `docs/adr/050-session-log-extraction-per-adapter.md` (this plan delivers it)
- Measured motivation: `reports/2026-07-25-aet-performance-observability-review.md` — all three
  Claude Code stage sessions in the archive carry 0 test runs and 0 tokens.
- Verified current behaviour (2026-07-26): `wirelog.extract_test_invocations`
  (`src/aet/wirelog.py:50`) globs `agents/*/wire.jsonl` under a kimi session dir, filters
  `record["type"] == "context.append_loop_event"`, pairs `tool.call`/`tool.result` on the call
  `uuid`, and reads epoch-millisecond `time`. Exit status comes from a
  `Command failed with exit code: (\d+)` trailer (`:42`) plus `isError`.
- `usage.parse_usage` (`src/aet/usage.py:43`) is the dispatch pattern this mirrors: one call
  site, `if agent_cli == "claude" … if agent_cli == "kimi" …`.
- Claude Code schema, verified 2026-07-26: `~/.claude/projects/<cwd-slug>/<sessionId>.jsonl`;
  assistant records carry `message.content[]` blocks of `type: "tool_use"` with `name: "Bash"`,
  `id`, `input.command`; the paired user record carries `type: "tool_result"` with
  `tool_use_id`, `is_error`, `content`. Every record carries `timestamp` (ISO-8601),
  `sessionId`, `cwd`, `gitBranch`. A throwaway extractor run against this schema during scope
  validation read 70 transcripts and paired 170 test-shaped Bash calls with correct durations —
  the schema is confirmed against real data, not inferred. The script was not kept; task 2 builds
  the reader as tested source against the committed fixture.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **One dispatched interface, keyed on `agent_cli`**, mirroring `usage.parse_usage`. Callers pass
  the CLI name and a session reference; they never name a schema, a path template, or a record
  type (ADR-050 decision 1).
- **The kimi reader moves behind the seam unchanged**, verified by replaying a captured session
  fixture for byte-identical output (R-4). This is the regression contract for the refactor.
- **The Claude reader is a peer, not a kimi variant.** It pairs on `tool_use_id`, parses
  ISO-8601 `timestamp` directly (no epoch-ms conversion), and derives exit status from the
  boolean `is_error` — mapped to `0`/non-zero, with `None` for unpaired calls. It does **not**
  reconstruct a kimi-shaped directory (ADR-050 decision 3).
- **Both readers return the same shape** — `{command, start_time, end_time, duration_seconds,
  exit_code}`, ISO-8601 UTC, ordered by start time, with null end/duration for unpaired calls.
  Nothing is estimated (the existing null contract, ADR-031).
- **Detection comes from `tap-02`'s registry**, so neither reader carries a runner list.
- **The Claude reader matches the kimi reader's hardening**: the `_MAX_WIRE_LINE_CHARS` cap,
  tolerant JSON decoding, `errors="replace"`, and `OSError` tolerance are properties of the
  interface, not of one implementation.
- **A missing reader is explicit** (ADR-050 decision 4): an adapter without one resolves to no
  session reference and emits nothing, as a stated and tested property.
- Session-reference *resolution* in the orchestrator is `tap-04`. This plan delivers readers and
  the dispatch, with resolution exercised through fixtures.

## Rejected Alternatives

- **One parser normalising both schemas** — rejected (ADR-050): differing record shapes, pairing
  keys, time bases, and failure signals would tangle both sets of assumptions in one function.
- **Land the seam with only the kimi reader** — rejected (ADR-050): an extension point with one
  implementation is speculative; the second reader is what proves the interface is general.
- **Have AET write its own normalised session log during the run** — rejected (ADR-050): it
  duplicates data the CLI already persists and fails exactly when it matters, on a crashed
  session.
- **Keep `wirelog` as the module name for both** — rejected: "wire" is kimi's schema term, and
  CONTEXT.md now reserves **Session Log** for the general concept.

## Task List

1. Add the session-reader interface with `agent_cli` dispatch and the shared invocation shape;
   move the kimi reader behind it — M (traces: R-4)
2. Add the Claude Code reader: transcript parsing, `tool_use`/`tool_result` pairing on
   `tool_use_id`, ISO-8601 timestamps, `is_error` → exit status, unpaired-call null contract —
   M (traces: R-5)
3. Apply the kimi reader's hardening (line cap, tolerant decode, `OSError` tolerance) to the
   Claude reader and assert it at the interface level — S (traces: R-5)
4. Capture and commit both session-log fixtures (kimi wire, Claude transcript), redacted — S
   (traces: R-4, R-5)
5. Tests (see Validation Steps) — M (traces: R-4, R-5)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: the seam plus both readers ship together by ADR-050's explicit decision, and
  are verifiable entirely against committed fixtures without any orchestrator change.
- Note: this plan is at the upper edge of M. If task 2 alone exceeds the M ceiling during
  implementation, mark it `⚠️ ATOMIC OVERSIZED` per ADR-046 rather than splitting the seam from
  its second implementation — the split is what the ADR rejects.

## Files to Modify

- `src/aet/session_log.py` (new — dispatch interface and shared invocation shape)
- `src/aet/wirelog.py` (kimi reader, moved behind the seam)
- `src/aet/session_log_claude.py` (new — Claude Code reader)
- `tests/fixtures/session_logs/kimi/wire.jsonl` (new)
- `tests/fixtures/session_logs/claude/transcript.jsonl` (new)
- `tests/session_log/test_session_log_dispatch.py` (new)
- `tests/wirelog/test_wirelog.py`
- `docs/telemetry-guide.md`

## Validation Steps

- [ ] `make validate` passes
- [ ] Coverage, in `tests/session_log/test_session_log_dispatch.py` — the seam, both readers, and
      both committed fixtures — with the kimi regression replay in `tests/wirelog/test_wirelog.py`:
  - `test_kimi_fixture_replay_matches_pre_change_output` (unit) — the R-4 regression contract
  - `test_dispatch_selects_reader_by_agent_cli` (unit)
  - `test_dispatch_returns_empty_for_adapter_without_reader` (unit) — ADR-050 decision 4
  - `test_claude_reader_pairs_tool_use_and_tool_result` (unit)
  - `test_claude_reader_derives_iso_timestamps_and_duration` (unit)
  - `test_claude_reader_maps_is_error_to_exit_status` (unit)
  - `test_claude_reader_emits_null_end_and_duration_for_unpaired_call` (unit)
  - `test_readers_tolerate_malformed_json_and_overlong_lines` (unit, both readers)
  - `test_claude_reader_ignores_non_bash_tool_use_blocks` (unit)
- [ ] R-trace coverage: R-4 by tasks 1, 4, 5; R-5 by tasks 2, 3, 4, 5; no unknown R-ids
- [ ] For the new parsing logic in `session_log_claude.py`, tests above name the coverage
- [ ] Security review: confirm the Claude reader resolves paths only under the expanded
      `~/.claude/projects/` root, never follows a session id containing path separators, and
      applies the same line-length and decode tolerance as the kimi reader
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; `wirelog.extract_test_invocations` returns as the single kimi-only entry
point and Claude sessions go back to emitting nothing. No telemetry schema change here and no
orchestrator wiring yet (`tap-04`), so the revert touches only extraction code and its fixtures.

---

*Stage: secure*
*Next step: run `aet-sync-docs`, then `aet-ship`*

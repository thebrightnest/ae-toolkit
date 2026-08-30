---
id: agy-orchestrator-adapter
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: Verifies that agy execution command and transcript resolution do not introduce path traversal or command injection risks.
docs_sync: required
docs_sync_reason: Updates CLI and telemetry docs to document agy adapter support.
---

# Plan: aet Orchestrator Adapter for agy CLI

## Context

- PRD: [`docs/prds/agy-adapter-prd.md`](../prds/agy-adapter-prd.md)
- ADR-050: Session-Log Extraction Is a Per-Adapter Extension Point (`docs/adr/050-session-log-extraction-per-adapter.md`)
- ADR-053 / ADR-062: Supervision Uniformity (`docs/adr/062-supervision-uniformity.md`)

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] Adds support for `agy` CLI in `cli_adapter.py`, `session_log.py`, `usage.py`, and adds `session_log_agy.py`

## Task List

1. Create `src/aet/session_log_agy.py` to extract test invocations and tool calls from Antigravity `transcript.jsonl` — M (traces: R-4)
2. Update `src/aet/session_log.py` to dispatch `agent_cli == "agy"` to `session_log_agy.extract_test_invocations` — S (traces: R-5)
3. Update `src/aet/usage.py` to support `agent_cli == "agy"`, parsing token counts from session transcripts or logs — S (traces: R-6)
4. Update `src/aet/cli_adapter.py` to register `agy` in `ADAPTERS` and implement session ref resolution for Antigravity conversation IDs — S (traces: R-1, R-2, R-3)
5. Create `tests/test_session_log_agy.py` and update `tests/cli/test_cli_adapter.py` and `tests/test_usage.py` with comprehensive unit and fixture tests — M (traces: R-7)

**Size definitions:**
- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 1 day OR > 600 lines

### Floor Check

- [ ] Expected diff is below the calibrated floor threshold (≤ 50 headline lines).
- [ ] The change is limited to one subsystem and maintains no architectural invariant.
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against.
- [ ] This is docs-only and its sole consumer is a single sibling.

*Floor check evaluation:* The feature touches multiple components of the adapter pipeline (`cli_adapter`, `session_log`, `session_log_agy`, `usage`, tests), delivering an end-to-end usable adapter without over-fragmentation.

## Rejected Alternatives

- **Embedding merge-guard hook generation for Antigravity in this plan** — rejected: merge guard hook generation is part of `harness_guard.py` (Phase 6 harness parity) and is decoupled from headless orchestrator CLI execution.
- **Parsing only standard output regexes without reading `transcript.jsonl`** — rejected: contradicts ADR-050, which mandates reading real session transcripts to prevent zero-observed-telemetry blind spots.

## Files to Modify

- `src/aet/session_log_agy.py` (create)
- `src/aet/session_log.py` (modify)
- `src/aet/usage.py` (modify)
- `src/aet/cli_adapter.py` (modify)
- `tests/test_session_log_agy.py` (create)
- `tests/cli/test_cli_adapter.py` (modify)

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Unit tests pass (`pytest tests/cli/test_cli_adapter.py tests/test_session_log_agy.py tests/test_usage.py`)
- [ ] Full test suite passes (`make test`)
- [ ] R-trace coverage: every in-scope R-id (R-1 through R-7) is covered by ≥ 1 task; no task cites an unknown R-id
- [ ] Specifically named test coverage:
  - `src/aet/session_log_agy.py` covered by `tests/test_session_log_agy.py::TestSessionLogAgy` (unit + fixture tests)
  - `src/aet/session_log.py` agy dispatch covered by `tests/test_session_log.py::TestSessionLogDispatch`
  - `src/aet/usage.py` agy parsing covered by `tests/test_usage.py::TestUsageAgy`
  - `src/aet/cli_adapter.py` agy adapter covered by `tests/cli/test_cli_adapter.py::TestCLIAdapter::test_agy_adapter` and `TestResolveSessionRef::test_agy_session_reference`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit introducing `agy` adapter files and dictionary entries. Existing `kimi` and `claude` adapters remain untouched and fully functional.

## Pipeline

`pipeline` is set to `standard` in frontmatter.

---

_Stage: plan-approved_

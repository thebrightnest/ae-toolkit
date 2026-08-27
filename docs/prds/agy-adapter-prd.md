# PRD: aet Orchestrator Adapter for agy CLI

*Stage: synced*
*Next step: run `aet-ship`*

## Overview

The Agentic Engineering Toolkit (AET) orchestrator executes stage sessions through pluggable agent CLIs (`src/aet/cli_adapter.py`). Currently, AET supports `kimi` and `claude`. This feature adds support for the `agy` CLI (Google Antigravity), allowing AET workflows (`aet run`, `aet run-one`) to run headless sessions with `agy`, capture usage tokens/costs, and extract real test-run telemetry from Antigravity session transcripts.

## Intake Triage

This is an **enhancement (new provider capability)** extending AET's pluggable adapter registry to support the `agy` CLI. It does not alter existing `kimi` or `claude` adapter semantics, preserving backward compatibility and ADR-050 parity.

## Goals

- **G-1**: Support `agy` as a first-class agent CLI in `src/aet/cli_adapter.py` with headless execution (`--dangerously-skip-permissions -p "<prompt>"`).
- **G-2**: Extract test-run invocations from `agy` conversation transcripts (`~/.gemini/antigravity-cli/brain/<conversation-id>/.system_generated/logs/transcript.jsonl`) achieving ADR-050 telemetry parity.
- **G-3**: Resolve `agy` session references (conversation IDs) from session output or runtime context to link telemetry records with conversation transcripts.
- **G-4**: Parse token usage metrics from `agy` sessions and integrate with `src/aet/usage.py`.
- **G-5**: Ensure full test coverage and automated verification for the `agy` adapter, transcript parser, and usage extractor.

## Non-Goals

- Implementing merge-guard hooks in `src/aet/harness_guard.py` for Antigravity settings/hooks (deferred to future harness-guard extensions).
- Supporting interactive `agy` sessions (AET orchestrator only drives headless/unattended executions).
- Modifying `agy` CLI binary or internal storage schemas.

## Requirements

- **R-1**: `src/aet/cli_adapter.py` defines `agy` in `ADAPTERS` with `bin="agy"`, `prompt_flag="-p"`, `headless_flag="--dangerously-skip-permissions"`, `workdir_flag=None`, `usage_mode="transcript"`, `stall_timeout=7200.0`, and `wall_backstop=7200.0`.
- **R-2**: `CLIAdapter.build_cmd` produces correct argv lists for `agy` invocations in headless mode (`["agy", "--dangerously-skip-permissions", "-p", prompt]`).
- **R-3**: `CLIAdapter.resolve_session_ref` extracts the `agy` conversation ID (UUID format) from output or environment and verifies the transcript exists.
- **R-4**: `src/aet/session_log_agy.py` implements `extract_test_invocations(conversation_id, worktree_dir=None, home=None)` to parse test runs from `transcript.jsonl`, extracting `run_command` tool calls with `created_at` timestamps, exit codes, output, and duration.
- **R-5**: `src/aet/session_log.py` dispatches `agent_cli == "agy"` to `session_log_agy.extract_test_invocations`.
- **R-6**: `src/aet/usage.py` supports `agent_cli == "agy"`, parsing token usage from session transcripts or output envelopes.
- **R-7**: Comprehensive test suite in `tests/cli/test_cli_adapter.py` and `tests/test_session_log_agy.py` covering invocation building, session ref resolution, transcript parsing, and error cases.

## User Stories

- As an engineer using Antigravity, I want AET orchestrator commands (`aet run`, `aet run-one`) to invoke `agy` headlessly so that my automated engineering pipelines run using `agy`. (satisfies: R-1, R-2)
- As an engineering lead, I want test telemetry from `agy` sessions to be accurately captured in AET telemetry records so that quality metrics reflect real test runs. (satisfies: R-4, R-5)
- As an operator, I want token consumption and conversation links from `agy` sessions to be recorded in stage telemetry for cost and trace tracking. (satisfies: R-3, R-6)

## Acceptance Criteria

- [x] `resolve_cli_adapter("agy")` returns the configured `agy` adapter. (satisfies: R-1)
- [x] `adapter.build_cmd("test prompt", headless=True)` returns `["agy", "--dangerously-skip-permissions", "-p", "test prompt"]`. (satisfies: R-2)
- [x] `adapter.resolve_session_ref` successfully parses conversation IDs from output and confirms transcript presence on disk. (satisfies: R-3)
- [x] `session_log_agy.extract_test_invocations` extracts `pytest` / test runner tool invocations from fixture transcripts with correct timestamps, durations, and exit statuses. (satisfies: R-4, R-5)
- [x] `usage.parse_usage("agy", ...)` parses token counts accurately from `agy` session logs. (satisfies: R-6)
- [x] `pytest tests/cli/test_cli_adapter.py tests/test_session_log_agy.py` passes cleanly with 100% assertion success. (satisfies: R-7)

## Technical Notes

- **Transcript Location**: By default, `agy` writes conversation logs under `~/.gemini/antigravity-cli/brain/<conversation-id>/.system_generated/logs/transcript.jsonl`.
- **Transcript Format**: JSONL lines containing step records. Steps of interest include `PLANNER_RESPONSE` steps with `tool_calls` invoking `run_command` (or terminal execution), paired with step results or status.
- **Defensive Parsing**: Following `wirelog.py` and `session_log_claude.py`, corrupted or non-standard JSON lines must be skipped gracefully without throwing exceptions.

## Open Questions

None. Core design clarified and aligned.

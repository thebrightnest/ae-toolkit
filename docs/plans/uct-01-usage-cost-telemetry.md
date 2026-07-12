---
id: uct-01-usage-cost-telemetry
size: M
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: captures and parses agent-CLI subprocess output (an LLM-adjacent trust boundary) into telemetry records — verify JSON-only parsing with input size caps and that captured text is never re-invoked as a shell command
docs_sync: required
docs_sync_reason: telemetry-log-schema.md gains populated-by semantics for token_count/cost_estimate plus new run-summary aggregate fields; panel README gains the cost view
---

# Plan: Usage & Cost Telemetry — Capture, Record, Display

## Context

- No PRD: sub-day instrumentation feature scoped interactively with the user (2026-07-12); the AGENTS.md PRD gate targets >1-day features. User requirement, verbatim: "I'm missing any info about costs in this panel" — tokens/USD must become visible in the telemetry panel.
- The schema already has the fields: `token_count` / `cost_estimate` on stage records (`aet-work/references/telemetry-log-schema.md:43`, accepted by `stage_record` at `aet-work/lib/telemetry.py:191`). But the only producer — `_emit_stage_session` (`aet-work/bin/orchestrator:279`) — never passes them. Verified 2026-07-12: all 83 stage records in the live archive (`~/.aet/telemetry`) carry `token_count: null, cost_estimate: null`. No API-call-count field exists anywhere.
- Root cause: `run_stage` (`aet-work/bin/orchestrator:402`) and `run_stage_group` (`aet-work/bin/orchestrator:466`) spawn the agent CLI via `subprocess.run(cmd, ...)` with inherited stdio — usage output streams to the terminal and is lost the moment the process exits.
- `cli_adapter.py:45-57` defines per-CLI adapters (`kimi`, `claude`) with `build_cmd(prompt, workdir, headless)` but declares no machine-readable usage mode per CLI.
- `run_summary_record` (`aet-work/lib/telemetry.py:224`) has no token/cost aggregates, so `last-run.json` cannot summarize a run's cost even once stage records carry data.
- The panel (`aet-work/panel/index.html`, single-file app reading `/api/list` + `/api/file` from `aet-work/panel/serve`) renders stage/run records with no cost column. The serve API needs no change — new fields flow through `/api/file` automatically.
- API-call counts are out of scope: neither CLI exposes them in headless output. Tokens + USD is the realistic target (confirmed with user).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **Live-tee capture, not `capture_output`.** Stage sessions run up to ~1 hour (observed: 3118s). Switching to `subprocess.run(capture_output=True)` would silence live agent output for the whole session — a regression for anyone watching a batch. Instead: `Popen(stdout=PIPE, stderr=STDOUT)` with a reader loop that echoes each line to the terminal live AND appends to a bounded buffer (keep last ~256 KB; usage blocks are emitted at exit). After exit, parse usage from the buffer.
- **Per-CLI usage strategies in a new `aet-work/lib/usage.py`.** `parse_usage(agent_cli: str, text: str) -> dict | None` returning `{"input_tokens": int, "output_tokens": int, "total_tokens": int, "cost_usd": float | None}` or `None` when nothing parseable was emitted. `claude` supports a headless JSON envelope (`-p --output-format json`) carrying `usage` + `total_cost_usd`; `kimi`'s headless usage output must be verified at implementation time (task 1). A CLI with no machine-readable mode records `null` — the schema already allows it. **Never fabricate estimates from prompt size or char counts.**
- **Adapters declare their mode.** `CLIAdapter` gains `usage_mode: str | None` (e.g. `"json-envelope"`, `"text-tail"`, `None`); `build_cmd` appends the flags the mode requires when headless.
- **Record wiring.** `run_stage`/`run_stage_group` return `(exit_code, usage)`; `_emit_stage_session` gains a `usage` param and passes `token_count=usage["total_tokens"]`, `cost_estimate=usage["cost_usd"]` into `stage_record` (signature already supports both).
- **Run-level aggregates.** `run_summary_record` gains `total_tokens: int | None` and `total_cost_usd: float | None`; the orchestrator computes them at batch end by summing non-null stage records (all-null → null, preserving today's shape for CLIs without usage modes).
- **Panel.** Run list and per-stage rows gain tokens + cost columns/aggregates; `null` renders as `—` so pre-change records and unsupported CLIs look intentional, not broken.
- **Backward compatible by construction.** Readers already tolerate null fields; old records need no migration.

## Rejected Alternatives

- **`capture_output=True` on the existing `subprocess.run`** — rejected: kills live session output for up to an hour; the tee-loop costs ~30 lines and preserves observability.
- **Token estimation from prompt/response char counts** — rejected: fabricated numbers are worse than null; the schema's null contract exists precisely for unmeasurable cases.
- **Adding an `api_calls` field** — rejected: no headless CLI exposes per-call counts; adding a permanently-null field is schema noise. Revisit if a CLI starts reporting it.
- **Splitting panel display into a second plan** — rejected: capture plumbing without its only consumer would ship invisible data; one coherent path (capture → record → display) fits one atomic plan (see Batching Check).

## Task List

1. Discovery + `aet-work/lib/usage.py` (TDD): verify `claude` and `kimi` headless usage output formats on this machine; implement `parse_usage` with per-CLI strategies, bounded tail scan, garbage-input → `None`; fixtures captured from real CLI output — M
2. `cli_adapter.py` + orchestrator capture: `usage_mode` on adapters; `run_stage`/`run_stage_group` move to Popen + live-tee reader, return `(exit_code, usage)` — M
3. Record wiring: `_emit_stage_session` passes usage into `stage_record`; `run_summary_record` gains `total_tokens`/`total_cost_usd`; batch end aggregates stage records — S
4. Panel + docs: tokens/cost columns and run aggregates in `aet-work/panel/index.html` with `—` null rendering; update `aet-work/references/telemetry-log-schema.md` (populated-by semantics + new summary fields) and `aet-work/panel/README.md` — S
5. Tests, live evidence, merge: `tests/test_usage_parsing.py` + orchestrator wiring test with a stub CLI; one real `aet run-one` session demonstrating non-null values end-to-end; merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with queued ewl-\* plans (distinct files, distinct risk surface; this plan is their blocker, not a batchmate)
- [x] Stays one plan despite touching capture + display: splitting would strand null-data plumbing from its only consumer (see Rejected Alternatives)

## Files to Modify

- `aet-work/lib/usage.py` (new)
- `aet-work/lib/cli_adapter.py`
- `aet-work/bin/orchestrator`
- `aet-work/lib/telemetry.py`
- `aet-work/references/telemetry-log-schema.md`
- `aet-work/panel/index.html`
- `aet-work/panel/README.md`
- `tests/test_usage_parsing.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] `tests/test_usage_parsing.py`: claude JSON-envelope fixture parses to tokens + cost; kimi fixture parses or returns `None` gracefully (per task 1 finding); garbage/truncated input → `None`; oversize input is tail-scanned, not loaded whole
- [ ] Orchestrator wiring test: stub CLI emitting a usage block produces a stage record with non-null `token_count`/`cost_estimate`, and the run summary carries the aggregates
- [ ] Live evidence: one real `aet run-one` session → stage `.jsonl` shows non-null `token_count`/`cost_estimate`, `last-run.json` shows `total_tokens`/`total_cost_usd`, panel renders both
- [ ] Backward compat: pre-change records (null fields) render `—` in the panel; `aet report` still runs against the old archive
- [ ] Live output preserved: batch run still streams agent output to the terminal in real time
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. All readers tolerate null `token_count`/`cost_estimate` (today's state), and the panel's `—` fallback keeps old and new archives renderable either way. No data migration exists to undo.

## Pipeline

`pipeline: standard` — TDD→implement→QA, review, CSO grouping is appropriate; the security-relevant surface (parsing subprocess output into stored records) is covered by the CSO stage plus the `security_review: required` checks above.

---

_Stage: qa-complete_
_Next step: run `aet-review`_

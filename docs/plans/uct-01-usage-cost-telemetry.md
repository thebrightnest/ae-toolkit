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
- **Correction (2026-07-12, reopens tasks 6–7):** task 1's "kimi emits no machine-readable usage" conclusion was wrong — it only checked stdout. Verified live on this machine (kimi 0.23.6): every kimi session writes real per-step usage to `~/.kimi-code/sessions/<workDirKey>/<sessionId>/agents/<agentId>/wire.jsonl`. Each LLM step lands as a `context.append_loop_event` envelope whose inner event is `{"type": "step.end", "uuid": …, "usage": {"inputOther", "output", "inputCacheRead", "inputCacheCreation"}, "finishReason": …}` — the same four token flavors claude's envelope gives. `~/.kimi-code/session_index.jsonl` maps `sessionId → sessionDir → workDir` (1,899 entries locally; both `ses_` and `session_` id prefixes exist and must be handled). This session's own wire held 91 `step.end` events at verification time; the uct-01 worktree session's wire held 44. Layout documented at <https://moonshotai.github.io/kimi-code/en/guides/sessions.md> and <https://moonshotai.github.io/kimi-code/en/configuration/data-locations.md>. The wire schema is a recovery/replay stream, not a documented public contract — pin the parser to the verified kimi version and re-verify on upgrade.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **Live-tee capture, not `capture_output`.** Stage sessions run up to ~1 hour (observed: 3118s). Switching to `subprocess.run(capture_output=True)` would silence live agent output for the whole session — a regression for anyone watching a batch. Instead: `Popen(stdout=PIPE, stderr=STDOUT)` with a reader loop that echoes each line to the terminal live AND appends to a bounded buffer (keep last ~256 KB; usage blocks are emitted at exit). After exit, parse usage from the buffer.
- **Per-CLI usage strategies in `aet-work/lib/usage.py`.** `parse_usage(agent_cli: str, text: str) -> dict | None` returning `{"input_tokens": int, "output_tokens": int, "total_tokens": int, "cost_usd": float | None}` or `None` when nothing parseable was emitted. `claude` uses the headless JSON envelope (`--output-format json`, final `type:"result"` element carries `usage` + `total_cost_usd`). A CLI with no usage source records `null` — the schema already allows it. **Never fabricate estimates from prompt or response size.**
- **Kimi strategy: post-exit wire-file parse (task 6).** Kimi prints no usage to stdout, so after the process exits: (1) extract the session id from the resume-hint line in the captured stdout (`kimi -r (session_|ses_)<id>`); (2) resolve the session dir via `~/.kimi-code/session_index.jsonl`, falling back to globbing `~/.kimi-code/sessions/*/<sessionId>/`; (3) parse every `agents/*/wire.jsonl` (main agent + subagents), unwrap `context.append_loop_event` envelopes, take inner events with `type == "step.end"`, dedupe by `uuid`; (4) `input_tokens = Σ(inputOther + inputCacheRead + inputCacheCreation)`, `output_tokens = Σ(output)` — exact provider counts, no estimation; (5) cost: no cost field exists anywhere in kimi output — derive from a small local price table in `usage.py` keyed by `modelAlias` (from the wire's `config.update` event) with a dated source comment; unknown or subscription-only models → `cost_usd: null`, never an invented number. The wire files are append-only JSONL read after process exit, so parsing is trivially race-free.
- **Adapters declare their mode.** `CLIAdapter` gains `usage_mode: str | None` (`"json-envelope"`, `"wire-file"`, `None`); `build_cmd` appends the flags the mode requires when headless (`wire-file` needs none — the tee already captures the resume-hint).
- **Record wiring.** `run_stage`/`run_stage_group` return `(exit_code, usage)`; `_emit_stage_session` gains a `usage` param and passes `token_count=usage["total_tokens"]`, `cost_estimate=usage["cost_usd"]` into `stage_record` (signature already supports both).
- **Run-level aggregates.** `run_summary_record` gains `total_tokens: int | None` and `total_cost_usd: float | None`; the orchestrator computes them at batch end by summing non-null stage records (all-null → null, preserving today's shape for CLIs without usage modes).
- **Panel.** Run list and per-stage rows gain tokens + cost columns/aggregates; `null` renders as `—` so pre-change records and unsupported CLIs look intentional, not broken.
- **Backward compatible by construction.** Readers already tolerate null fields; old records need no migration.

## Rejected Alternatives

- **`capture_output=True` on the existing `subprocess.run`** — rejected: kills live session output for up to an hour; the tee-loop costs ~30 lines and preserves observability.
- **Token estimation from prompt/response char counts** — rejected: fabricated numbers are worse than null; the schema's null contract exists precisely for unmeasurable cases.
- **Adding an `api_calls` field** — rejected: no headless CLI exposes per-call counts; adding a permanently-null field is schema noise. Revisit if a CLI starts reporting it.
- **Splitting panel display into a second plan** — rejected: capture plumbing without its only consumer would ship invisible data; one coherent path (capture → record → display) fits one atomic plan (see Batching Check).
- **Reading `wire.jsonl` live during the kimi session** — rejected: mid-run parsing races the appending writer for zero benefit; the usage totals are only needed after exit, when the file is final and the read is trivially safe.
- **`kimi export <sessionId>` ZIP as the parse source** — rejected: an extra CLI invocation and archive handling to obtain files already readable at a stable local path; revisit only if the sessions directory layout becomes inaccessible.

## Task List

1. ✓ Discovery + `aet-work/lib/usage.py` (TDD): verified headless usage output formats — `claude` json-envelope carries `usage` + `total_cost_usd`; `kimi` emits no machine-readable usage **on stdout** (2026-07-12). `parse_usage` with bounded tail scan, garbage-input → `None`; fixtures in `tests/test_usage_parsing.py`. _(kimi conclusion superseded — see Context correction and task 6: usage exists on disk in wire.jsonl)_
2. ✓ `cli_adapter.py` + orchestrator capture: `usage_mode` on adapters; `run_stage`/`run_stage_group` moved to Popen + live-tee reader, return `(exit_code, usage)`
3. ✓ Record wiring: `_emit_stage_session` passes usage into `stage_record`; `run_summary_record` gained `total_tokens`/`total_cost_usd`; batch end aggregates stage records (`_usage_aggregates`)
4. ✓ Panel + docs: tokens/cost columns and run aggregates in `aet-work/panel/index.html` with `—` null rendering; `aet-work/references/telemetry-log-schema.md` and `aet-work/panel/README.md` updated
5. ✓ Tests + live evidence: `tests/test_usage_parsing.py` + orchestrator wiring tests with a stub Popen CLI; panel cost view CDP-verified at QA (553 tests). Merge step executes at `aet-ship` per pipeline
6. ✓ Kimi wire-file usage strategy (TDD): session id from the resume-hint in captured stdout; session dir via `session_index.jsonl` (fallback glob); parse `agents/*/wire.jsonl` unwrapping `context.append_loop_event`, sum `step.end` usage deduped by `uuid`; `modelAlias` → price-table cost derivation (null when unknown/unpriced — `kimi-code/kimi-for-coding` is subscription/quota-billed with no published per-token price, verified 2026-07-13); fixtures from real wire files (both `ses_`/`session_` prefixes, multi-agent, duplicate-uuid case) — M
7. ✓ Adapter + docs correction: kimi `usage_mode: "wire-file"`; corrected the now-wrong "kimi has no usage" claims in `cli_adapter.py` comments, `usage.py` docstring, `tests/test_usage_parsing.py` fixtures/comments, and panel README/schema doc populated-by notes; live evidence — a real kimi stage recorded `token_count: 70181` in its stage `.jsonl`, matching a manual sum of that session's `wire.jsonl` `step.end` events (2026-07-13) — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with queued ewl-\* plans (distinct files, distinct risk surface; this plan is their blocker, not a batchmate)
- [x] Stays one plan despite touching capture + display: splitting would strand null-data plumbing from its only consumer (see Rejected Alternatives)

## Files to Modify

- `aet-work/lib/usage.py`
- `aet-work/lib/cli_adapter.py`
- `aet-work/bin/orchestrator`
- `aet-work/lib/telemetry.py`
- `aet-work/references/telemetry-log-schema.md`
- `aet-work/panel/index.html`
- `aet-work/panel/README.md`
- `tests/test_usage_parsing.py`

## Validation Steps

- [x] `make validate` passes; full suite passes
- [x] `tests/test_usage_parsing.py`: claude JSON-envelope fixture parses to tokens + cost; kimi wire fixture (main + subagent wire files) sums `step.end` usage with uuid dedupe; `ses_` and `session_` id prefixes both resolve; missing session/index → `None` gracefully; unknown modelAlias → `cost_usd: null`; garbage/truncated input → `None`; oversize input is tail-scanned, not loaded whole
- [x] Orchestrator wiring test: stub CLI emitting a usage block produces a stage record with non-null `token_count`/`cost_estimate`, and the run summary carries the aggregates
- [x] Live evidence (claude or stub): stage `.jsonl` shows non-null `token_count`/`cost_estimate`, `last-run.json` shows `total_tokens`/`total_cost_usd`, panel renders both
- [x] Live evidence (kimi): one real kimi stage session → stage `.jsonl` shows non-null `token_count` matching a manual sum of that session's `wire.jsonl` `step.end` events (70181 tokens, 2026-07-13)
- [x] Backward compat: pre-change records (null fields) render `—` in the panel; `aet report` still runs against the old archive
- [x] Live output preserved: batch run still streams agent output to the terminal in real time (observed during the kimi live-evidence run, 2026-07-13)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. All readers tolerate null `token_count`/`cost_estimate` (today's state), and the panel's `—` fallback keeps old and new archives renderable either way. No data migration exists to undo.

## Pipeline

`pipeline: standard` — TDD→implement→QA, review, CSO grouping is appropriate; the security-relevant surface (parsing subprocess output into stored records) is covered by the CSO stage plus the `security_review: required` checks above.

---

_Stage: secure_
_Next step: run `aet-sync-docs`, then `aet-ship`_

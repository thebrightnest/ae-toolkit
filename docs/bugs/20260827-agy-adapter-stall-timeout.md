# Bug Report: every `agy` stage session dies at ~300s on turn 1, classified `flaky`

## Metadata

- **Reported:** 2026-08-27
- **Severity:** high — no task using the `agy` adapter completed any work
- **Status:** fixed 2026-08-27 (timeout); stream-format change still open

## Symptoms

Seven stage attempts across four tasks in two runs, every one dead at
approximately 300 seconds with `num_turns: 1` and no output:

| Task | Attempt | Duration | Reported error |
| --- | --- | --- | --- |
| poh-01 | 1 | 293.5s | `The stream was interrupted. Please continue the task you were working on.` |
| poh-01 | 2 | 298.4s | `timeout waiting for response` |
| poh-02 | 1, 2 | ~300s | same pair |
| poh-04 | 1, 2 | ~300s | same pair |
| poh-03 | 1 | 285.1s | `timeout waiting for response` |

Every attempt recorded `commits_created: 0`, `files_modified: []`,
`result: "failure"`, `exit_code: 1`. Every worktree was left clean at its base
commit. No task produced a single line of work.

The tasks were marked `failed` with `failure_class: "flaky"` and
`failure_signature: null`.

## Reproduction Steps

1. Configure the `agy` agent CLI as the adapter.
2. Run any task whose stage prompt is large — the observed sessions read
   159k–226k input tokens with 1.5M+ cache reads.
3. Observe the stage session.

Observed: the session dies at ~300s having taken one turn. Expected: the session
runs to completion, or the kill is classified as a timeout rather than a flake.

## Root Cause

`agy --print-timeout` defaults to **`5m0s`**, and AET never passed the flag.

```
--print-timeout   Timeout for print mode wait (default 5m0s)
```

The stage totals confirm it — the *stage* wall is pinned at 302-314s on every
attempt even where agy's own internal counter varies:

| Task | Attempt | agy internal | stage total |
| --- | --- | --- | --- |
| poh-01 | 1 / 2 | 293.5s / 298.4s | 303.1s / 303.4s |
| poh-02 | 1 / 2 | 297.0s / 213.9s | 302.7s / 314.5s |
| poh-03 | 1 | 285.1s | 302.4s |
| poh-04 | 1 / 2 | 294.3s / 292.0s | 302.8s / 302.4s |

**An earlier revision of this report blamed an AET per-adapter default under
ADR-053. That was wrong.** This adapter's `stall_timeout` and `wall_backstop`
are both `7200.0` (`src/aet/cli_adapter.py`), 24x looser than the CLI's own
deadline, so AET's supervision never came close to firing. The kill came from
inside `agy`, which is why it arrived as an ERROR envelope on the CLI's own
stdout rather than as a signal death.

The loss is total rather than partial because of the *output format*. With
`--output-format json` the CLI buffers the entire response and emits one blob at
the end, so a print-mode abort yields `"response":""` — every token produced is
discarded. Roughly 6.8M tokens across seven attempts returned no output at all.

## Fix Applied

`build_cmd` now passes `--print-timeout`, derived from the adapter's own
`stall_timeout` rather than written as an independent number:

```python
cmd.extend(["--print-timeout", f"{int(self.stall_timeout)}s"])
```

Deriving it is the point. A CLI deadline settable independently of the
supervisor's ceiling is the whole defect; two numbers that can drift would
reproduce it the next time either moved. Verified that `agy` accepts both
`7200s` and `2h0m0s`.

## Consequences

- No work completed. Four tasks consumed roughly 6.8M tokens across seven
  attempts and produced nothing.
- **Misclassified as `flaky`, so the retry policy made it worse.** A flake is
  worth retrying; a deterministic ceiling is not. Each task burned its retry on
  a second attempt that failed identically, at full prompt cost.
- The zero-commit branches this leaves are the input to a second defect:
  `aet state reset` derives `merged` from their ancestry
  (`docs/bugs/20260827-reset-derives-merged-from-zero-commit-ancestry.md`).
  Together the two would have settled three unimplemented tasks as done.

## Still Open: the output format

The timeout fix stops the abort. It does not change the fact that an abort
loses everything, and that is a separate property of `--output-format json`.

`agy` also offers `--output-format stream-json`, and its terminal `result` event
carries a payload **identical** to the `json` envelope — same
`conversation_id`, `status`, `response`, `duration_seconds`, `num_turns`, and
`usage` block. Verified 2026-08-27 against agy 1.1.22:

```
{"event":"init","conversation_id":"...","init":{"cwd":"...","tools":[...]}}
{"event":"step_update","step_update":{"step_index":1,"state":"ACTIVE",
   "step_type":"agent_response","text_delta":"OK"}}
{"event":"result","result":{"conversation_id":"...","status":"SUCCESS",
   "usage":{...}}}
```

What that would buy:

- **Partial work survives an abort.** Output arrives incrementally instead of in
  one terminal blob.
- **A real liveness signal.** `step_update` events are exactly the run-log
  writes the hybrid-liveness model wants, rather than inferring life from
  process-tree activity.
- **Progress visibility.** Every failed record here reads `num_turns: 1` with no
  further detail; `step_index` and `step_type` would show where a session
  actually stopped.

What it costs:

- `usage.parse_usage`'s `json-envelope` mode parses stdout as a single JSON
  object. Stream mode needs it to take the last `event: "result"` line — the
  same fields, one level deeper.
- `_resolve_agy_session_id` reads `conversation_id` from the envelope; in stream
  mode it is available earlier, on the `init` event.
- `_USAGE_MODE_FLAGS` needs a mode whose flag is `stream-json`.

Not applied here: it changes a parser contract shared with the usage and
session-log layers, which is more than a timeout fix should carry.

## Notes

Recorded telemetry is in
`~/.aet/telemetry/aiskills/main/2026-08-27/run-20260827-130856-7wpfxtsl/` and
`run-20260827-135813-7pfikgnf/`. The `test_run` records in those files show
`result: "unknown"` with a null `end_time`, consistent with the session dying
mid-command rather than a suite reporting failures.

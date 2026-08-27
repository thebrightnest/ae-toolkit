# Bug Report: every `agy` stage session dies at ~300s on turn 1, classified `flaky`

## Metadata

- **Reported:** 2026-08-27
- **Severity:** high — no task using the `agy` adapter completed any work
- **Status:** fixed 2026-08-27 — timeout, output format, and classification

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

## Fix Applied: the timeout

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
- **Misclassified as `flaky`.** A flake is transient; a deadline is
  deterministic. **Correction:** an earlier revision of this report claimed the
  misclassification cost the second attempt. It did not —
  `_TRIAGE_DEFAULT_ACTIONS` routes both `flaky` and `timeout` to `requeue`, and
  `append_failure_if_countable` counts both as breaker evidence, so the retry
  would have happened either way. The cost was diagnostic: the telemetry
  described a deterministic ceiling as a transient fault, which is what made the
  run's own records misleading about their cause.
- The zero-commit branches this leaves are the input to a second defect:
  `aet state reset` derives `merged` from their ancestry
  (`docs/bugs/20260827-reset-derives-merged-from-zero-commit-ancestry.md`).
  Together the two would have settled three unimplemented tasks as done.

## Fix Applied: the output format

`--output-format json` buffers the whole response, so the abort printed
`"response":""` and discarded every token produced. The adapter now requests
`stream-json`, whose terminal `result` event carries a payload **identical** to
the buffered envelope — verified against agy 1.1.22:

```
{"event":"init","conversation_id":"...","init":{"cwd":"...","tools":[...]}}
{"event":"step_update","step_update":{"step_index":1,"state":"ACTIVE",
   "step_type":"agent_response","text_delta":"OK"}}
{"event":"result","result":{"conversation_id":"...","status":"SUCCESS",
   "usage":{...}}}
```

`_find_agy_result_event` unwraps that event, and `_find_agy_envelope` prefers it
when present, falling back to the buffered shape. One parser serves both modes,
so older captures still parse. The preference matters: a stream's `init` and
`step_update` objects also carry a `conversation_id` but no usage block, so
taking the last object merely *mentioning* one would parse no usage at all.

An aborted stream now yields no usage — correctly, none exists — while still
resolving its conversation id from the `init` event, so the session log stays
reachable for diagnosis.

## Fix Applied: the classification

`_ADAPTER_TIMEOUT_PATTERNS` classifies a CLI-reported deadline as `TIMEOUT`
rather than letting it fall through the exit-code branch to `FLAKY`. It sits
after the throttle check, because a rate-limited session can hang until the
deadline expires and waiting for the window is the more specific remedy, and
before the environment check, because a deadline tail often carries transport
words. The patterns are space-qualified, so a test named
`test_timeout_waiting_for_response` still classifies as `DESIGN`.

## Still Open: is an adapter deadline the task's fault?

`append_failure_if_countable` excludes `canceled` and `throttled` from circuit
breaker evidence on the grounds that they say nothing about the task. An adapter
deadline arguably belongs with them — three sessions killed by a CLI's own
default say nothing about the plan either, yet they count toward quarantining
it. Not changed here: the exclusion set is ADR-030's, and widening it is a
decision about the breaker's contract rather than a classification fix.

## Notes

Recorded telemetry is in
`~/.aet/telemetry/aiskills/main/2026-08-27/run-20260827-130856-7wpfxtsl/` and
`run-20260827-135813-7pfikgnf/`. The `test_run` records in those files show
`result: "unknown"` with a null `end_time`, consistent with the session dying
mid-command rather than a suite reporting failures.

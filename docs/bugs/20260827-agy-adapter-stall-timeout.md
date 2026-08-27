# Bug Report: every `agy` stage session dies at ~300s on turn 1, classified `flaky`

## Metadata

- **Reported:** 2026-08-27
- **Severity:** high — no task using the `agy` adapter completed any work
- **Status:** open

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

Not established. Three things are known and one is suspicious.

Known:

- The wall is consistent. Seven attempts, 285–298 seconds, never longer. A
  consistent ceiling across independent sessions is a configured limit, not a
  provider fluctuation.
- `num_turns: 1` on every attempt. The session never completed its first turn,
  so this is not a stall mid-task; it is a first response that never arrived.
- Both error strings come from the adapter's own JSON envelope, not from the
  orchestrator, so the adapter observed the failure and reported it.

Suspicious: ADR-053 removed `--stall-timeout` from `run`/`run-one` and made it a
per-adapter default. A ~300s per-adapter default applied to a first turn that
legitimately takes longer — these prompts are large — would produce exactly this
signature. The `agy` adapter's default and whether it measures inter-token
silence or total elapsed time both need checking.

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

## Fix Direction

Two separable pieces.

**Classification, independent of the cause.** A session that dies at the adapter
timeout is a timeout, not a flake — ADR-060 already holds that signal death is a
timeout, and this is the same argument for an adapter-reported deadline. The
distinction is not cosmetic: it decides whether a retry is spent. A retry that
reproduces the previous attempt's duration to within a few seconds is evidence
the failure is deterministic, and is available to the classifier.

**The timeout itself.** Establish the `agy` adapter's effective default, whether
it is elapsed-time or silence-based, and whether it is reachable by a legitimate
large first turn. If a large prompt can exhaust it, the default is wrong for the
prompt sizes the orchestrator produces.

## Notes

Recorded telemetry is in
`~/.aet/telemetry/aiskills/main/2026-08-27/run-20260827-130856-7wpfxtsl/` and
`run-20260827-135813-7pfikgnf/`. The `test_run` records in those files show
`result: "unknown"` with a null `end_time`, consistent with the session dying
mid-command rather than a suite reporting failures.

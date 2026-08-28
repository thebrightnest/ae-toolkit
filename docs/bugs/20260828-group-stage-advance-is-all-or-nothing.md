# Bug Report: a session group records its stage only at the group boundary, so partial progress is invisible

## Metadata

- **Reported:** 2026-08-28
- **Severity:** medium (repeats completed work on every retry of a grouped stage)
- **Status:** open

## Symptoms

Reported from the consuming repository (`dhl-agentic-tot`, task `pub-03`): the
implement commit `098f828` — 22 files, +1389/−222 — landed on the branch during
the first attempt. Every one of the following 21 attempts was still prompted
with `Current stage: plan-approved. Target stage: implemented` and re-ran
`aet-tdd → aet-implement` over finished work.

Setting the stage by hand (`aet state set-stage … implemented`) resolved it: the
resumed run picked `aet-qa` for `implemented → qa-complete` and redid nothing.

## Reproduction Steps

1. Run a task whose workflow groups `plan-approved` and `implemented` into one
   session (the `software` default, `workflows/software.json`
   `execution_policy.session_groups[0]`).
2. Let the implement half commit, then kill the session, or let its `qa` verdict
   be missing.
3. Re-run the task.

Observed: the prompt names `plan-approved` as the current stage and the group
starts again from `aet-tdd`.

## Root Cause

The stage is not reset on requeue — it is never advanced. `_record_stage` is
called once for the whole group, after every evidence gate in the group span has
a schema-valid passing verdict (`orchestrator.py:1876-1898`):

```python
for stage in runnable:
    ...
    if not _require_passing_verdict(...):
        return False

if not _record_stage(task, expected_final, repo_root):
```

`expected_final` is the group's final target, so a group that dies anywhere
inside its span leaves the task record at the group's entry stage no matter how
many of its stages completed. Nothing in `_requeue_task`
(`orchestrator.py:2521-2544`) or `cli/aet_state.py` touches `stage`; the value
read back on the next attempt is the one that was never written.

The `stage` field on every failure signature is the same artefact seen from the
other side: a group failure records `stage=stages[0].name`
(`orchestrator.py:1600`) regardless of which stage in the group was running, so
the signatures cannot be used to tell how far the group got either.

## Consequences

The cost of a retry is the whole group, not the failed remainder, and the agent
is handed a worktree whose state contradicts its instructions — implement is
complete, and the prompt asks for it. Where a retry loop is also in play, every
iteration pays for the completed stages again.

## Fix Direction

Record each stage inside a group as it completes, rather than once at the group
boundary. The per-stage evidence gate already runs in the loop at
`orchestrator.py:1876`, which is the point where a stage is known to be
finished; advancing there makes group execution resumable at stage granularity
and leaves `expected_final` as an assertion rather than the only write.

Recomputing the stage from git on requeue is the weaker alternative: it infers
from commits what the evidence gates already know exactly, and it has no answer
for a stage that produces no commit.

`verify_stage_advancement` (`orchestrator.py:1902`) compares against
`expected_final` and needs the same treatment, or it will refuse the
intermediate writes.

## Prior Art

This is the third recorded mechanism for one symptom, "a resume re-runs
completed stages", and the second time its cost has been measured at roughly
$24. `aet-toolkit-defects.md` D2 (plan overlay regresses the worktree footer,
~$24 on `poc-03a`, 2026-08-12) and D3 (`_record_stage` no-ops under the
`git-refs` backend, so the record never carries a stage) both produced it by
other routes. D3 is fixed in the current tree — `_record_stage`
(`orchestrator.py:308-350`) resolves the task ref and routes through
`aet state set-stage` — and D2 was patched in the consuming install.

The recurrence argues for a test at the symptom rather than at each mechanism: a
task whose group dies after a completed stage must not be handed a prompt naming
that stage as pending.

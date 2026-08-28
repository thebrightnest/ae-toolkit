# Bug Report: a session group records its stage only at the group boundary, so partial progress is invisible

## Metadata

- **Reported:** 2026-08-28
- **Severity:** medium (repeats completed work on every retry of a grouped stage)
- **Status:** fixed 2026-08-28 (ADR-069)

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

## What The Record Actually Showed

The stage is not written late — it is never reached. The group's record step sits
after `if exit_code != 0: return False`, so a failed session skips it entirely.
The question is therefore not *when* to write the stage but **what may credit a
stage whose session failed**, which ADR-069 decides.

## Fix

`_credit_proven_stages` runs on the group's failure path. It walks the group's
span in order and credits each stage whose own evidence verdict passes, stopping
at the first stage it cannot prove. Nothing is inferred:

- A stage with no evidence binding — `plan-approved`, the one in the field case —
  is never credited. Its artifact is commits, and a commit does not distinguish
  finished from interrupted.
- What the branch does carry goes to the run's handoff note via
  `_note_branch_state`: the commits since `base_commit`, the verdicts already
  recorded, and the stage if one was credited. The retry's prompt already renders
  that note, so the next session is told what exists instead of the record
  claiming a stage it cannot prove.
- Crediting reads verdicts and never spawns a session. Asking an agent for a
  missing verdict stays on the success path.

The success-path record at the group boundary is unchanged, so
`verify_stage_advancement` still asserts what it always did.

## Consequence For The Field Case

A group of `[reviewed, secure, synced]` that dies in `sync-docs` now keeps its
security review. The measured case — `plan-approved` dying after the implement
commit — is *not* fixed by advancing the record, deliberately: the retry is told
the commit exists rather than being credited with a stage nothing proved. See
ADR-069's Alternatives Considered for why crediting from commits was rejected.

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

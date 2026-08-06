---
id: lop-03-closure-fails-closed-on-missing-plan
size: S
work_class: normal
blocked_by: []
pipeline: standard
status: queued
security_review: skipped
security_review_reason: changes only the guard condition and error path of an existing commit/push call; introduces no new inputs, no new command construction, no new file writes, and no new external surface
docs_sync: required
docs_sync_reason: closure gains a new refusal an operator can hit, which belongs in the ship/closure documentation alongside the existing push-failure message
---

# Plan: Closure Fails Closed When the Plan File Cannot Be Resolved

## Context

- PRD: `docs/prds/local-only-plans-prd.md` (R-6)
- ADR-034 (`docs/adr/034-settled-from-versioned-plan-data.md`) makes the plan's
  committed `status` the authoritative settled signal. This plan makes closure
  actually honour that guarantee instead of reporting success when it cannot.
- ADR-054 (`docs/adr/054-plan-documents-are-outside-the-durability-gate.md`)
  revises ADR-034 decision 3 so that *terminal* status writes remain committed
  and pushed. This plan is what makes that surviving guarantee enforceable.

**Verified current behaviour (2026-08-05):** in `cmd_record_merge`
(`src/aet/cli/aet_state.py`), the closure write is guarded at `:1119` by
`if plan_path and Path(plan_path).exists():`. When `plan_path` is falsy or the
file is absent **and** no explicit `--plan` was passed, control falls through
both branches to `:1138`, which prints `Recorded merge for {task_id}` and
returns `0`. The merge is recorded in state, but the plan's terminal `status`
is never written, committed, or pushed — and the operator is told it succeeded.
The neighbouring paths are already strict: an explicit `--plan` that does not
resolve returns `1` at `:1130-1135`, and a push failure returns non-zero at
`:1122-1128`. Only the silent-fallthrough case is wrong.

## Intake Triage

- [x] Confirmed this is a **reproducible defect**, not a feature — deleting the
  plan file before `record-merge` reproduces "Recorded merge" with exit 0 and
  no status write. It is planned here rather than routed to `aet-bug-report`
  because it is a named requirement (R-6) of an approved PRD whose other plans
  widen its blast radius, and shipping the fix separately from that PRD would
  detach it from the reasoning that found it.

## Locked design

- **Fail closed, name the remedy.** When the plan cannot be resolved from the
  checkout or from the merged branch, closure prints what it looked for, where,
  and how to fix it, and returns non-zero. It does not guess a path and it does
  not proceed silently.
- **Resolution is attempted before refusing.** The plan may legitimately be
  absent from the working checkout while present on the merged branch — that is
  the normal state immediately after a squash merge in some flows. Closure
  therefore resolves against the merged branch before concluding the plan is
  gone, so the new refusal cannot fire on a healthy closure.
- **The merge record itself is unaffected.** State-level merge recording already
  happened by this point and stays recorded; the non-zero exit reports that the
  *plan status write* did not complete, matching the existing push-failure
  message's "recoverable on re-run" framing.
- **Independent of the rest of the PRD.** This carries no dependency on
  `lop-01` or `lop-02` and can ship in either order. It is separated so a
  defect fix in the closure path is reviewed on its own terms rather than
  inside a behaviour change that removes a durability gate.

## Rejected Alternatives

- **Fold this into `lop-02`** — rejected: different risk profile and different
  reviewer attention; a correctness fix in the closure path should not land
  inside a change that creates commits in task branches.
- **Route to `aet-bug-report` instead of planning it** — rejected: it is R-6 of
  an approved PRD, and detaching it would lose the reasoning that surfaced it.
- **Warn loudly but keep exit 0** — rejected: closure is consumed by unattended
  runs where nothing reads warnings; a task whose terminal status never landed
  is not a successful closure.
- **Infer the plan path from the task id when it is missing** — rejected: it
  guesses at exactly the moment the system has lost track of the truth, and a
  wrong guess writes `merged` to the wrong plan.

## Task List

1. Resolve the plan from the merged branch when it is absent from the checkout,
   so the new refusal cannot fire on a healthy closure — S (traces: R-6)
2. Replace the silent fallthrough at `aet_state.py:1119` with a fail-closed
   branch that names what was sought, where, and the remedy, and returns
   non-zero — S (traces: R-6)
3. Tests: deleting the plan before `record-merge` fails with the named remedy
   instead of "Recorded merge"; a plan resolvable only from the merged branch
   still closes successfully; the existing explicit-`--plan` and push-failure
   paths are unchanged — S (traces: R-6)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: a defect fix in one guard with its own reproduction and
  regression test, shippable in any order relative to `lop-01`/`lop-02`.
- [ ] Expected diff materially exceeds branch/PR overhead: **no** — this is a
  small diff. Justification for keeping it separate anyway: it is a correctness
  fix on the closure path with a different risk profile from the two behaviour
  changes, and folding it into either would bury a defect fix inside a change
  that removes a durability gate.
- [x] Cannot share a branch with related tasks: it has no dependency on them
  and blocking it behind `lop-01` would delay a fix that stands on its own.

## Files to Modify

- `src/aet/cli/aet_state.py` (`cmd_record_merge` guard and resolution)
- `tests/state/` — closure resolution and refusal coverage
- `skills/aet-work/references/queue-commands.md` (`record-merge` — the new
  refusal joins the documented push-failure outcome)
- `docs/PIPELINE.md` (closure outcomes)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-6 covered by tasks 1–3
- [ ] New source files: none introduced
- [ ] Unit: guard condition and message. Integration: `record-merge` against a
      real repo with the plan deleted, and with the plan present only on the
      merged branch
- [ ] Regression: existing explicit-`--plan` failure and push-failure paths
      keep their current exit codes and messages
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the branch. The change is confined to one guard and its error path, with
no data-format or state change. Reverting restores the silent-success behaviour;
any closure that failed under the new refusal is re-runnable, since the merge
record itself is never rolled back.

## Pipeline

`standard` — raised from the `minimal` size default (S) at scope validation.
The change is small, but it sits on the closure path that writes terminal
status, which is the one durability guarantee ADR-054 leaves standing. The
defect being fixed is *silent success*; a regression in the fix reintroduces
silence, so the change earns a separate review and CSO pass over an isolated
implementation stage.

---

*Stage: reviewed*
*Next step: run `aet-sync-docs`*

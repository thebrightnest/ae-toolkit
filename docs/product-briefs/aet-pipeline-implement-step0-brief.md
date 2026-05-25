# aet-pipeline-implement Step 0 Approval Checkpoint — Discovery Brief

## Idea

Evaluate whether the Step 0 approval checkpoint in `aet-pipeline-implement` provides value or should be removed.

## Diagnostic Route

Pure engineering/infra improvement → Q2, Q4 only.

## Findings

### Q2 — Status Quo

**Question:** What are users doing right now when they hit the Step 0 approval checkpoint?

**Answer:** Users manually approve every time. The checkpoint has become routine friction with no real decision-making value.

**Push:** When was the last time you said _no_ at that checkpoint?

**Answer:** Never.

**Implication:** The checkpoint is a speed bump, not a guardrail. It interrupts flow without ever changing behavior. The `AET_EXECUTION_MODE=unattended` escape hatch exists but is rarely used because users forget to set it or don't know about it. The default experience is purely additive friction.

### Q4 — Narrowest Wedge

**Question:** What's the smallest change that removes this friction?

**Answer:** Delete Step 0 entirely.

**Implication:** The checkpoint serves no purpose that isn't already covered by:

- The plan.md being in `plan-approved` or `scope-validated` stage (human approval already happened)
- `aet-ship`'s own pre-merge validation gate (final check before merging)
- Individual skill gates within the pipeline (e.g., aet-review's hard gate on architecture issues)

## Verdict: KILL

The Step 0 approval checkpoint in `aet-pipeline-implement` should be **removed entirely**.

It duplicates approval logic that already exists upstream (plan approval) and downstream (aet-ship, aet-review). It has never prevented a user from proceeding. It violates the pipeline's promise of "one entry point — from approved plan to reviewed, secure, synced branch ready for aet-ship."

If users want unattended execution, the pipeline should default to flowing through. If they want a gate, they can run individual skills instead of the pipeline.

## Assignment

Delete the "Step 0 — Approval checkpoint" section from `aet-pipeline-implement/SKILL.md`. Remove references to `AET_EXECUTION_MODE` from that skill. The pipeline should begin directly at Step 1 (aet-tdd).

---

_Stage: brief-validated_
_Next step: proceed with removal_

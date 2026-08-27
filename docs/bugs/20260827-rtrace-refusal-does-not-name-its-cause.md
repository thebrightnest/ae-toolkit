# Bug Report: the rtrace intake refusal does not name the one cause it cannot resolve

## Metadata

- **Reported:** 2026-08-27
- **Severity:** low
- **Status:** fixed 2026-08-27

## Symptoms

A plan whose deliverable is to introduce a requirement is refused at intake:

```
⛔ Refusing to promote dep-06-preflight-subcommand-plan.md: intake validation failed.
  - rtrace: task cites unknown requirement R-84
```

The message describes the plan as citing something that does not exist. The plan
is correct: minting `R-84` is what it delivers. No wording distinguishes this
from the case the check is actually for — a typo, or a citation of a requirement
that was renumbered.

## Reproduction Steps

1. Write a plan whose task list cites an R-id absent from its PRD, where the plan
   itself adds that requirement.
2. Run `aet sprint add` on it.

Observed: refusal naming the R-id as unknown, with no indication that the check
cannot pass for this class of plan.

## Root Cause

`rtrace_findings` (`src/aet/plan_validate.py:320-350`) reads the requirement set
from the PRD as it stands:

```python
required = _requirements_rids(prd)
...
for rid in sorted(task_rids - required):
    findings.append(Finding("rtrace", plan, f"task cites unknown requirement {rid}"))
```

The register is treated as static for the life of a plan. Where the convention is
that implementation appends to it, a plan introducing a requirement can never
satisfy the check, and the message does not say so.

The escape already exists and is already named. `_add`
(`src/aet/cli/sprint.py:190-194`) prints the ack syntax on every refusal:

```
  Fix the plan, or override a check that does not apply by adding a line to it:
    ⚠️ VALIDATE ACK: <check-id> — <reason>
```

So the gap is not a missing mechanism. It is that the operator cannot tell from
the message which of the two situations they are in, and both wrong fixes are
attractive: pre-minting the anchor in the register moves the plan's deliverable
outside the plan, and padding `(traces: …)` annotations to satisfy coverage makes
the annotations false.

## Consequences

Bounded, and paid once per plan of this shape. The correct action — an ack line
with a reason — is available immediately, but reaching it requires knowing that
the check has a class of input it cannot accept.

## Fix Direction

When the only rtrace findings for a plan are `cites unknown requirement`, add one
line naming the cause: the check compares citations against requirements that
already exist, so a plan that introduces one cannot satisfy it, and an ack is the
intended route when the requirement is the plan's own deliverable.

Considered and not proposed here: letting a plan declare the R-ids it introduces,
so the check resolves them. That needs a convention for the declaration, and the
same outcome is reached by allocating the anchor in the register at plan-approval
time — which also serialises anchor allocation before a parallel batch and
removes the duplicate-anchor collision seen on 2026-08-27. The convention change
belongs to the consuming repository, not the toolkit.

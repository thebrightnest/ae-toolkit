# Product Brief: [Feature / Initiative Name]

## Problem

One paragraph: the user or system pain this addresses, and why it matters now.

## Context

Background a reader needs to evaluate the requirements: current behavior, prior
decisions (link to ADRs / briefs), and constraints. Note any relevant prior art
or rejected directions that shaped the scope.

## Requirements

Number every requirement so it can be traced forward into the PRD and plan tasks
and backward to the problem it solves. Each requirement must be **independently
testable** — state observable behavior, not implementation.

- **R-1**: [Observable capability the system must provide; verifiable on its own.]
- **R-2**: [A second, independently testable capability.]
- **R-3**: [Add as many as the scope needs; keep each one atomic.]

## Non-Requirements

Explicitly out of scope. Naming these prevents scope creep and gives reviewers a
place to point when a task drifts.

- [Thing this brief deliberately does not cover, and why.]

## Rejected Alternatives

Record each serious alternative that was considered and the reason it was not
chosen. This is the institutional memory that stops settled debates from
re-opening.

- **[Alternative A]** — rejected: [reason — e.g., duplicates work owned by a later
  phase; higher cost for no added signal; contradicts ADR-NNN.]
- **[Alternative B]** — rejected: [reason.]

## Success Signal

The smallest observable change that proves the brief landed. One or two bullets
— a reviewer should be able to check this without reading the whole document.

- [Concrete, checkable signal tied to one or more R-ids above.]

---

_Stage: brief-draft_
_Next step: run `aet-plan`_

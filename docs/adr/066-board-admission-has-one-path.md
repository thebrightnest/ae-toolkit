---
subject: board-admission
relates: [19, 55, 61]
---

# Board Admission Has One Path

## Status

Accepted (2026-08-27). Relates to ADR-019 (Structured Gate Evidence), whose
decision 4 this makes auditable; ADR-055 (Settled-ness Lives in a Commutative
Provenance Ledger); and ADR-061 (The Record Is the Plan After Intake), whose
intake handoff this gives a single implementation. Implements the
`single-admission-path` PRD (`docs/prds/single-admission-path-prd.md`).

## Context

ADR-019 decision 4 stated that the plan footer `*Stage:*` "is demoted to a human
breadcrumb everywhere; no gating decision reads it." ADR-055 removed `status`
from the plan contract. ADR-061 made the task record the sole source of the spec
after intake and named `aet sprint add` as the single handoff.

On 2026-08-27, running the planning pipeline end to end found that intake still
refused any plan whose body lacked the literal footer `_Stage: plan-approved_`.
Three accepted decisions had been in force and the violating read had survived
all three.

It survived because there was nothing to violate in one place. Admission —
building a new task from a plan file and putting it on the board — is performed
at two doors, `aet sprint add` and `aet sprint intake`, and each inlined its own
sequence of checks. Auditing "does any gating decision read the footer?" meant
finding all six `stage_from_plan` call sites and classifying each as a gate or a
breadcrumb, a distinction not visible at the call. Three were gates, three were
not, and the classification lived in no artifact.

The divergence that produced was not symmetric. Measured before remediation:

| Policy | `sprint add` | `sprint intake` | `backlog add` |
| --- | --- | --- | --- |
| Already queued / already settled | yes | yes | n/a |
| Footer stage is `plan-approved` | yes | yes | `{plan-draft, plan-approved}` |
| Frontmatter contract, rtrace, acks | yes | **no** | no |

The only policy every door shared was the one the ADRs forbid. The policy the
ADRs want — the `plan_validate` suite — ran at one door only, so a plan
reachable from an `aet:sprint` issue reached the board with nothing checked
while the identical plan was refused at the other door. That defect was filed
and fixed separately; it is recorded here as evidence of the mechanism, not as
the subject.

Duplicated policy with no canonical site drifts, and the drift is invisible
until someone exercises both paths with the same input. This is the same shape
as two other 2026-08 findings: an instruction ahead of its enforcement, and a
sweep reported complete while copies survived.

## Decision

**Admission to the board is one operation. Doors call it; doors do not implement
it.**

1. **One operation decides.** A single function determines whether a plan may
   join the board and returns the built task or the reasons it was refused.
   `aet sprint add` and `aet sprint intake` obtain their decision from it and
   contain no admission policy of their own. A future third door adds a caller,
   never a policy.
2. **The outcome set is enumerable.** The operation's return type names every
   admission outcome — admitted, skipped as already live or already settled, or
   refused with reasons. Adding a reason requires editing that type, so "what
   can refuse a plan?" is answered by reading one definition rather than by
   grep.
3. **Presentation stays with the door.** The decision is shared; its rendering
   is not. `add` exits with a message and a status code; `intake` collects a row
   per candidate in a batch summary. Distinct ledger `source` values
   (`sprint-add`, `sprint-intake`) are likewise preserved — ADR-055 decision 2
   derives event ids from `source:task:kind:ref`, so collapsing them would
   change event identity.
4. **The operation does not read the plan footer.** The approval signal is the
   operator's invocation for `add` and the `aet:sprint` label for `intake` —
   both deliberate human acts on a specific plan. This is ADR-019 decision 4
   applied, not revisited. It is placed here so that conformance is a property
   of one function.

The decision this ADR adds is the *singularity*, not the disposition. What
authorizes a plan onto the board was already decided three times; where that
answer lives was not decided at all.

## Consequences

- **Easier:** ADR-019 decision 4 becomes auditable. "Does a gating decision read
  the footer?" is answered by reading the admission operation, not by
  classifying six call sites.
- **Easier:** A policy change lands once. The next ADR touching admission has
  one edit site.
- **Easier:** The two doors cannot disagree about the same plan, which was the
  operator-visible symptom.
- **Harder:** A door wanting genuinely door-specific admission behaviour must
  extend the shared outcome type rather than add a local check. This is the
  intended cost — a local check is exactly how the divergence arose.
- **Neutral:** `aet backlog add` stops gating on the footer so the property
  holds without exception. Its accepted set spanned the whole authoring
  lifecycle, so the removed check admitted every plan written from the template;
  the change costs no real gate and buys an absolute property.
- **Neutral:** Display and fallback readers are untouched. `gate.py`'s
  categorization, `context.py`'s reporting, and `verifier.read_plan_stage`'s
  post-record fallback remain; ADR-019 permits breadcrumb reads.

## Alternatives Considered

1. **Remove the footer read from each gating site, and stop there** — Rejected.
   It fixes the reported symptom and leaves N sites that can drift again. It
   also leaves the audit question as expensive as it was, which is what let the
   read survive three ADRs.
2. **Put admission in `plan_parser.py`, which owns `new_task_from_plan`** —
   Rejected. That module turns text into structures; admission is a policy
   decision needing the board, the history and the validation suite. Placing it
   there inverts the layering by making the parser depend on `plan_validate` and
   the backends.
3. **Put admission in `sprint.py`, where both doors already live** — Rejected.
   `backlog.py` and any future door would then import from a CLI command module.
   The operation belongs at the domain layer beside `plan_parser.py` and
   `plan_validate.py`.
4. **A registry or plugin interface for doors** — Rejected. There are two doors.
   A function both call carries the invariant; an extension point would add
   indirection without adding a caller.
5. **Leave `aet backlog add` reading the footer as a legitimate Author-phase
   read** — Rejected, though it is the most defensible alternative: backlog is
   pre-intake, and ADR-061 does say the plan file is the artifact during
   authoring. It loses to a narrower argument — the check accepts
   `{plan-draft, plan-approved}`, the entire authoring lifecycle, so it gates
   nothing while costing the audit a permanent exception.

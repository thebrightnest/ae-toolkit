# Bug Report: board admission is gated on footer prose in a file the model says is not authoritative

## Metadata

- **Reported:** 2026-08-27
- **Severity:** medium
- **Status:** planned 2026-08-27 — `adm-01`/`adm-02`/`adm-03` under ADR-066
- **Related:** `docs/retros/2026-08-27-planning-pipeline-contradictions-retro.md`
  (Finding 1), which closed this at the skill layer only.

## Symptoms

`aet sprint add` refuses a well-formed, human-approved plan unless the file body
contains the literal footer `_Stage: plan-approved_`:

```
⛔ Refusing to promote poh-01-…: plan stage is 'unknown';
   only 'plan-approved' plans may enter the sprint.
```

A plan authored by a skill that has stopped emitting the footer is unqueueable,
with no indication that a missing line in the body is the cause.

## Reproduction Steps

1. Write a valid plan in `docs/plans/` with complete frontmatter and no
   `_Stage:_` footer.
2. Run `aet sprint add docs/plans/<id>.md`.

Observed: refusal naming the stage as `unknown`. Adding the footer line admits
the same plan unchanged otherwise.

## Root Cause

`_add` (`src/aet/cli/sprint.py:140-146`) resolves the stage through
`stage_from_plan` (`src/aet/plan_parser.py:176-189`), which is a regex over the
file text:

```python
matches = re.findall(r"[*_]Stage:\s*([\w-]+)[*_]", content)
```

That footer is the only source. No frontmatter key, task record, or command flag
can supply the stage at intake, so admission to the board depends on a prose line
in the plan document.

Two accepted decisions say that document is not authoritative:

- **ADR-055** removed `status` from the plan contract and moved settled-ness to
  the ledger and task record. `CONTEXT.md` **Status (plan lifecycle)** records the
  unmet half in as many words: *"Settled-ness is derived by Settled-ness
  Authority, which still reads the plan footer as one of its three inputs — so
  `_Stage:_` is not yet a breadcrumb only, despite ADR-055's intent."*
- **ADR-061** makes the task record the sole source of the spec after intake, and
  `docs/plans/*.md` is gitignored precisely because the file is an
  authoring-phase artifact.

## Consequences

- A skill that correctly stops emitting the footer produces plans the CLI
  rejects. Observed on 2026-08-27: `aet-plan`'s completion protocol forbade the
  footer while intake required it, and the pipeline worked only because
  `.agents/templates/plan-template.md` still emitted it and won by accident.
- The 2026-08-23 sweep that removed the footer from skills and templates cannot
  be completed while this read exists. One emitter is now load-bearing.
- The retro's skill-layer fix documents the contradiction rather than removing
  it, and carries a note that must be retired when this is fixed.

## Update, 2026-08-27

Two things changed after this was filed.

**The disposition is not open.** This report cites ADR-055 and ADR-061 and
presents three candidate dispositions. It missed the one that decides the matter
literally — **ADR-019 decision 4**, accepted long before either: *"The plan
footer `*Stage:*` is demoted to a human breadcrumb everywhere; no gating decision
reads it."* With three accepted, live ADRs pointing the same way, "treat the
invocation as the approval" is not the smallest of three options; it is the only
conforming one. The `aet-pipeline-plan` intake triage routed the disposition out
as a conformance defect rather than a planning target.

**A worse defect was hiding behind it.** Admission happens at two doors —
`aet sprint add` and `aet sprint intake` — and each inlined its own check
sequence. The footer read was the only policy both shared. The `plan_validate`
suite ran at `add` only, so a plan reachable from an `aet:sprint` issue reached
the board with its frontmatter contract, rtrace citations, coverage and acks
never checked, while the identical plan was refused at the other door. Fixed in
`9aa5c7b4`, verified by removal: without it the regression test reports
`✓ Admitted feat-bad (#9) to the sprint` for a plan citing an absent R-id.

That gap is why the remaining work is not "delete the footer read". Removing it
from each gating site leaves N sites that can drift again, and leaves the
ADR-019 audit as expensive as it was — grep six `stage_from_plan` call sites and
classify each as gate or breadcrumb. The generative cause is that admission has
no canonical site. **ADR-066 (Board Admission Has One Path)** decides the
singularity, and `docs/prds/single-admission-path-prd.md` carries the work as
`adm-01` (the admission operation, footer read gone), `adm-02` (`aet backlog add`
stops gating on it), and `adm-03` (retire the three emitters and correct
`CONTEXT.md`).

One further finding from scope validation: **no code writes the plan footer.**
`update_plan_footer()` is absent from `src/`, so the footer is produced only by
templates and a skill instruction, and consumed only by gates. Once both ends
go, it does not become a breadcrumb — it ceases to exist for new plans.

## Fix Direction (as filed)

Three options, in the order they seem worth considering.

**Treat the invocation as the approval.** A human typing `aet sprint add <plan>`
is already the approval signal the footer check stands in for. Dropping the stage
gate entirely — keeping the frontmatter-contract and rtrace validation that
follow it — removes the proxy rather than relocating it. This is the smallest
change and the most consistent with ADR-055's intent.

**Move the stage into frontmatter.** Keeps an explicit approval marker but puts it
in the machine contract `intake_validation_errors` already validates, rather than
in prose. Costs a frontmatter key and a migration for existing plans.

**Keep the read and document it.** Rejected: it is today's state, and it is what
made the two-sided drift possible.

Whichever is chosen, retire the temporary note added to
`skills/aet-plan/SKILL.md` completion item 2, and finish the footer sweep across
`skills/` and `.agents/templates/`.

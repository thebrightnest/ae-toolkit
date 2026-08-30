---
id: adm-03-retire-the-plan-footer-emitters
size: S
work_class: normal
blocked_by:
  - adm-01-single-admission-operation
pipeline: standard
security_review: skipped
security_review_reason: Documentation and template text only; no executable code changes.
docs_sync: skipped
docs_sync_reason: This plan is itself the documentation correction; a divergence summary would restate it.
---

# Plan: Retire the Plan Footer Emitters

## Context

PRD: docs/prds/single-admission-path-prd.md
Decision: ADR-066 (Board Admission Has One Path).

Once `adm-01` lands, nothing reads the plan `_Stage:_` footer to make a
decision. Scope validation established that nothing *writes* it either:
`update_plan_footer()` is absent from `src/`, and the only `_Stage:` hits under
`src/` are a docstring in `plan_parser.py` and two console prints. The footer is
produced solely by three template and skill files.

Leaving them is worse than the original bug. `skills/aet-plan/SKILL.md`
completion item 2 currently *instructs* agents to write the footer and cites the
intake check as its reason — an instruction to satisfy a requirement that will
no longer exist, which is the 2026-08-27 retro's failure mode with the sign
flipped.

The sweep constraint is the point of this plan. Most `*Stage:*` occurrences
under `skills/` belong to the **PRD and brief lifecycles**, which `aet context`
still reads and which must survive untouched. The 2026-08-23 learning records
this exact sweep being reported complete while wrong copies survived, so the
method is: grep the whole tree and classify each hit by lifecycle, never walk a
hand-built file list.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The stale instruction is a documentation correction that falls out of
      `adm-01`, not an independently reproducible defect

## Task List

1. Remove the plan footer from the three emitters — `.agents/templates/plan-template.md`,
   `skills/aet-plan/SKILL.md`, and `skills/aet-setup/examples/plan-template.md.example` — S
   (traces: R-8)
2. Retire `skills/aet-plan/SKILL.md` completion item 2's instruction to write the
   footer and its citation of the intake check, and retire the temporary note the
   2026-08-27 retro added — S (traces: R-9)
3. Correct the `CONTEXT.md` **Status (plan lifecycle)**, **Plan File**, **Stage**
   and **Board** entries: the first says the footer is "not yet a breadcrumb
   only", the next two claim code maintains it when no writer exists, and the
   last names `aet sprint add` as the only door — S (traces: R-9, R-12)
4. Grep `skills/` and `.agents/templates/` for every remaining `Stage:` hit and
   confirm each surviving one belongs to the PRD or brief lifecycle:
   `aet-sync-docs/SKILL.md`, `prd-template.md.example`, `brief-template.md`, and
   `aet-validate-scope/SKILL.md` — S (traces: R-8)
5. Merge branch to main and verify integration — S

### Floor Check

- [x] Expected diff is below the calibrated floor threshold (≤ 50 headline lines)
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling it is ordered against
- [x] This is docs-only and its sole consumer is a single sibling

Two boxes checked, so the Floor Check says merge unless justified. Justification:
this is a cross-tree sweep whose whole risk is that it gets done carelessly at
the tail of a larger task, which is precisely how the 2026-08-23 sweep was
reported complete while eight references survived. Its acceptance criterion is a
grep over `skills/` that must return only PRD and brief footers — a check that is
legible as a task of its own and easy to wave through as step 8 of another. It is
also the only plan here that touches `skills/`, so merging it would widen a code
plan into the skills tree.

## Rejected Alternatives

- **Fold into `adm-01`** — rejected: see the Floor Check justification.
- **Merge with the `.agents/work-queue.json` reference audit** in
  `docs/TECHNICAL_DEBT.md` — rejected: shares a method (per-file judgment across
  `skills/`) but not a subject, producing one task verifiable only against two
  unrelated criteria. Recorded in the PRD's Non-Goals.
- **A blind `grep -r` replace of `*Stage:*` across `skills/`** — rejected: it
  would strip PRD and brief footers that `aet context` reads, breaking stage
  reporting. This is the specific corruption the sweep constraint exists to
  prevent.
- **Rewrite existing `docs/plans/*.md` files to drop their footers** — rejected:
  they are gitignored authoring artifacts (ADR-061) and an unread footer is
  inert. Churn with no consumer.

## Files to Modify

- `.agents/templates/plan-template.md`
- `skills/aet-plan/SKILL.md`
- `skills/aet-setup/examples/plan-template.md.example`
- `CONTEXT.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] No new source file is introduced by this plan
- [ ] `grep -rn '_Stage:\|\*Stage:' skills/ .agents/templates/` returns only PRD and brief footers
- [ ] `aet context` still reports `active_prd_stage` on a repo whose PRD carries a footer
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The templates resume emitting a footer that nothing reads,
which is inert rather than harmful.

## Pipeline

`standard`.

---

_Stage: plan-approved_

---
id: trp-06-skills-state-the-phase-model
size: M
work_class: normal
blocked_by:
  - trp-01-post-intake-consumer-audit
  - trp-02-ship-reads-the-record
pipeline: standard
security_review: skipped
security_review_reason: Documentation and skill prose only; no executable surface.
docs_sync: required
docs_sync_reason: This plan is the documentation sync for the whole PRD.
---

# Plan: Skills State the Phase Model

## Context

- PRD: `docs/prds/the-record-is-the-plan-prd.md` (R-8, R-10)
- Decision: ADR-061 (the record is the plan after intake)

19 files across 12 skills reference `docs/plans`. Many are correct — plans *are*
authored to `docs/plans/<id>.md`. The stale ones are those describing the world
after intake, and `aet-ship/SKILL.md:31` is the known example: "A bare task id
given to `aet ship` … resolves to the conventional `docs/plans/<task_id>.md`
path."

Command names are not the problem — every `aet` command the skills reference
exists. The problem is the model: which phase a skill is operating in, and
therefore whether the file or the record is its source.

Blocked by `trp-01` (the register says which consumers are post-intake) and
`trp-02` (ship's contract must be settled before it is documented).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] Stale documentation is not a code defect

## Task List

1. **Correct the `CONTEXT.md` glossary** so it states what the code does. Four
   entries are pre-R-19: **Task** ("one atomic `docs/plans/*.md` file"),
   **Plan File** ("the source of truth for intent"), **Work Queue** ("rebuilt by
   `aet init-queue` from `docs/plans/*.md`" — that command no longer exists), and
   **Settled-ness Authority** (names `_is_settled_from_authority` in
   `src/aet/cli/init_queue.py`; neither exists, and one of its three inputs is a
   plan-file footer R-19 makes impossible) — M (traces: R-10)
2. **State the three-phase model once** — author, intake handoff, post-intake —
   in `CONTEXT.md`, citing ADR-061, so skills reference it rather than restating
   it — S (traces: R-8, R-10)
3. **Classify all 19 `docs/plans` references** as authoring (correct) or
   post-intake (stale), using `trp-01`'s register — M (traces: R-8)
4. **Correct every stale reference**, beginning with `aet-ship/SKILL.md:31` — M
   (traces: R-8)
5. **Update `docs/CLI.md`** for ship's task-id-only contract — S (traces: R-8)
5. **Verify no skill instructs an agent to read or pass a plan path after
   intake** — S (traces: R-8)
7. Merge branch to main and verify integration — S

## Floor Check

- [x] Expected diff is below the calibrated floor threshold
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against
- [x] This is docs-only and its sole consumer is a single sibling

Two boxes, so a justification is owed. The fourth signal is arguable: the prose
is consumed by every agent session, not by a sibling plan. The natural merge
target would be `trp-02`, but `trp-02` is a critical change to the merge gate,
and bundling a 19-file prose sweep behind that verdict would mean a
documentation edit could fail a security review of the ship path. Kept separate,
and last, so it documents what actually landed rather than what was planned.

## Rejected Alternatives

- **Fold into `trp-02`** — rejected: see Floor Check.
- **Update `aet-ship/SKILL.md` only** — rejected: 11 other skills reference
  `docs/plans`, and the model, not the sentence, is what is stale.
- **Document both sources as valid** — rejected: that is the split the PRD
  removes.

## Files to Modify

- `CONTEXT.md`
- `docs/CLI.md`
- `skills/aet-ship/SKILL.md` and references
- `skills/aet-work/`, `skills/aet-implement/`, `skills/aet-review/`,
  `skills/aet-sync-docs/` (post-intake references)

## Validation Steps

- [ ] Lint passes (`aet docs`, markdownlint)
- [ ] R-trace coverage: R-8 (2,3,4,5,6), R-10 (1,2)
- [ ] `CONTEXT.md` states the three phases and the handoff point, citing ADR-061
- [ ] No `CONTEXT.md` entry defines a Task as a plan file, or the Plan File as
      the source of truth for intent
- [ ] The Settled-ness Authority entry names code that exists
- [ ] Every `docs/plans` reference is classified, with stale ones corrected
- [ ] No skill instructs reading or passing a plan path after intake
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Prose returns to describing the pre-R-19 model while the code
implements the post-R-19 one — today's state.

## Pipeline

`standard`.

---

_Stage: plan-approved_

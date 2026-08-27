# Retro: two instructions in the planning pipeline contradict the code that enforces them

**Date:** 2026-08-27 · **Trigger:** running `aet-pipeline-plan` end to end on a
three-item PRD · **Layer:** `skills/aet-plan/SKILL.md`

## Retro Debt

| Prior action item | Status | Evidence |
| --- | --- | --- |
| No further `aet-evolve` edit warranted; metrics evidence step is in the retro procedure | ✅ complete | This retro ran `aet metrics` per the procedure |
| Preserve `work_class` and `size` in `work-history.jsonl` so `aet metrics` can produce a per-class breakdown | ✅ complete | `aet metrics` now buckets by class — `critical 66.7% (2/3)`, `normal 0.0% (0/6)`, no `unclassified` rows. The 2026-07-26 retro recorded this as merged-but-purpose-unmet at 65/65 unclassified. |

## Metrics Evidence

`aet metrics` over settled tasks:

| Measure | Value |
| --- | --- |
| First-pass merge rate | 22.2% (2/9 merged) |
| Rework units | 44 |
| Cost per merged task | $3.52 avg (3 known) |

The numbers did not drive either finding below. Both were found by following the
skills and hitting the code.

## Finding 1 — the plan footer is banned by the skill and required by intake

`aet-plan`'s completion protocol said *"Do not write a `*Stage:*` footer into
plan.md."* `aet sprint add` resolves the stage through `stage_from_plan`
(`src/aet/plan_parser.py:176-189`), which reads that footer and nothing else, and
refuses any plan whose stage is not `plan-approved`
(`src/aet/cli/sprint.py:140-146`).

An agent following the skill therefore produces plans that cannot enter the
sprint. The system worked only because `.agents/templates/plan-template.md` — the
sole remaining emitter of the footer — contradicts the skill and wins in practice.

The instruction is not wrong about intent. ADR-055 makes the footer a breadcrumb,
and `CONTEXT.md` **Status (plan lifecycle)** already records that the code has not
caught up: *"`_Stage:_` is not yet a breadcrumb only, despite ADR-055's intent."*
The instruction is ahead of the code, and an instruction ahead of its enforcement
is indistinguishable from a wrong one at the point of use.

A recorded learning from 2026-08-23 describes the sweep that removed the footer
from skills, and notes that the sweep missed emitters in templates and reference
files. This is the same sweep, seen from the other side: the skills were changed
and the intake check was not.

## Finding 2 — `aet-plan` contradicts itself on intake

Two instructions in the same file:

- `create-stories` step 9: *"do not add them to the sprint automatically …
  Instruct the user to add plans explicitly with `aet sprint add`."*
- Completion protocol item 5: *"Confirm the new plan files were explicitly added
  to `.agents/work-queue.json` with `aet sprint add`."*

Item 5 asks the agent to confirm an action step 9 forbids it from taking. It also
confirms it against `.agents/work-queue.json`, a path the `git-refs` backend no
longer writes — the board is `refs/aet/tasks/*`.

The apparent conflict with `aet-pipeline-plan` Step 3, which does run
`aet sprint add` per plan, is downstream of this: with step 9 and item 5
disagreeing, there is no stated rule about who owns intake, so the pipeline's
behaviour reads as a third position rather than the sanctioned one.

## Layer and Fix

Both live in `skills/aet-plan/SKILL.md`. Applied:

- Completion item 2 now instructs writing `_Stage: plan-approved_`, cites the
  intake check that requires it, and records that the requirement is temporary
  and why.
- Completion item 5 now states that this skill does not run `aet sprint add`, and
  names the operator or `aet-pipeline-plan` Step 3 as the owner — which resolves
  the internal contradiction and the cross-skill one together.

## Deferred, with reason

**The stale `.agents/work-queue.json` path spans 15 files across 6 skills.** Not
swept here. Some occurrences are correct: `aet-work/references/migration-aet-state.md`
and `upgrading-existing-project.md` describe migrating *from* that layout, where
naming the old path is the point. A blind replace would corrupt them, and the
2026-08-23 learning is precisely about sweeps that report complete while wrong
copies survive. This needs per-file judgment and belongs in its own task.

**The intake check should stop reading the footer.** Finding 1 is closed at the
skill layer only; the code half is the durable fix and is not an `aet-evolve`
change.

## Action Items

| Item | Owner | Status |
| --- | --- | --- |
| Correct the two `aet-plan` instructions | this retro | ✅ applied |
| `make install-skills` so the installed copy matches the repo | operator | open |
| Per-file audit of `.agents/work-queue.json` references across `skills/` | queue | open |
| Remove the footer read from `stage_from_plan`'s intake use, per ADR-055 | queue | open |

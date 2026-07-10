# PRD: Roadmap Phase 0 — Record the Decisions

## Overview

Phase 0 of the AET roadmap (`content/fable-review/09-2026-07-10-roadmap.md`): write the two ADRs that everything downstream cites, and upgrade the planning templates with numbered-requirements tracing (fable-review 07, steal 7). Both decisions were already made in discussion (docs 06/08; owner decision 2026-07-10) — this phase turns them into citable records. Prose and templates only; no engine code.

## Goals

- **G1**: ADR-020 records "Scheduling is delegable; sequencing is not; the CLI is the enforcement boundary," including the multi-harness formulation (substitutability, enforced in the repo, proven on the scoreboard).
- **G2**: ADR-021 records "Evolve in place; the greenfield is trigger-gated," with the rationale and the four re-opening triggers.
- **G3**: Briefs, PRDs, and plans carry numbered requirements (R-1…) traced brief → PRD → plan task, with rejected alternatives recorded — enforced by template structure and `aet-plan` prose.

## Non-Goals

- No engine/CLI code changes (Phase 1+ owns workflow-as-data and the `aet` binary).
- No mechanized R-trace validation — `aet plan validate` is Phase 4; here the discipline lives in templates and skill prose.
- No `aet-validate-scope` R-lens changes (same Phase 4 rationale).
- No retrofit of existing briefs/PRDs/plans to the new format.

## Requirements

_This PRD adopts R-numbering ahead of the template change, deliberately — it is the first demonstration of the discipline it introduces._

- **R-1**: `docs/adr/020-*.md` states the enforcement-boundary decision: scheduling/compute delegable; sequencing, state legality, and gate evidence never delegated; the CLI is where they are enforced; includes the placement razor and the route-once-at-plan-time principle.
- **R-2**: ADR-020 includes the multi-harness section: inbound/outbound split, conformance tiers (`supported` = CI-green), routing as config — formulation: substitutability, enforced in the repo, proven on the scoreboard.
- **R-3**: `docs/adr/021-*.md` records evolve-in-place: the frh-completion context, the owner's 2026-07-10 rationale, and the demotion of the doc 08 greenfield to a design study.
- **R-4**: ADR-021 lists the four re-opening triggers and the convergence commitment (evolve toward doc 08's shape so a future port is a translation).
- **R-5**: `docs/adr/README.md` indexes both new ADRs in the existing format.
- **R-6**: `.agents/templates/brief-template.md` exists (new) with numbered Requirements and Rejected Alternatives sections.
- **R-7**: `prd-template.md` gains a Requirements section (R-numbered) with the instruction that user stories and acceptance criteria cite R-ids.
- **R-8**: `plan-template.md` task lines carry `(traces: R-n)`; the plan gains a Rejected Alternatives section and an R-coverage validation step.
- **R-9**: `aet-plan/SKILL.md` references R-numbering in `create-prd`/`create-stories`/`plan`, and the self-consistency lint gains an R-trace coverage check; `aet-pipeline-plan/SKILL.md` notes the enforcement in Step 1.
- **R-10**: `plan-template.md`'s frontmatter example includes the lifecycle `status` field (CONTEXT.md's plan-lifecycle model expects it; the template's omission was found during scope validation).

## User Stories

- As a planning agent, I want the enforcement-boundary principle in an ADR (R-1, R-2) so scope validation and future plans cite a stable record instead of a discussion doc.
- As the owner, I want the evolve-in-place decision and its triggers on the record (R-3, R-4) so the greenfield fork cannot silently re-open.
- As a plan reviewer, I want every plan task to cite R-ids (R-6–R-9) so coverage gaps are visible at review time instead of after implementation.

## Acceptance Criteria

- [ ] Both ADRs merged to main (ancestry-verified), indexed, `make validate` green (R-1…R-5).
- [ ] The three templates exist/are updated as specified (R-6…R-8, R-10).
- [ ] `aet-plan` prose updated with the R-trace lint check (R-9).
- [ ] The first planning cycle after merge (expected: roadmap Phase 1) produces a PRD with R-numbered requirements and plans whose tasks cite them — the roadmap's P0 exit gate, verified at that session.

## Technical Notes

- ADR numbers **020/021** are free (019 is latest). Follow house style per `019-structured-gate-evidence.md` and `000-template.md`.
- Skills and templates are symlinked live-on-merge — changes take effect for the next planning session with no packaging step.
- Batching: the two ADRs share one plan (near-identical doc additions sharing the README index — avoids a two-task chain over one index file). Template + prose changes form the second plan (they alter future planning behavior, warranting review isolation and `pipeline: standard`).
- Intake triage: enhancement — no reproducible defect involved; classification recorded here.

## Open Questions

None blocking. Flagged choices for owner review: `rdm-01` runs `pipeline: minimal` (static docs whose full content is locked in the plan); `rdm-02` runs `standard`.

---

_Stage: scope-validated_
_Validated: 2026-07-10_
_Next step: run `aet-work` (single-plan or multi-task queue)_

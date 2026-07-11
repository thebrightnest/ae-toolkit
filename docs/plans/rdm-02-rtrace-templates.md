---
id: rdm-02-rtrace-templates
size: M
blocked_by: []
pipeline: standard
status: approved
---

# Plan: Requirements Tracing — Brief/PRD/Plan Templates and aet-plan Prose

## Context

- PRD: `docs/prds/roadmap-p0-decision-records-prd.md` (G3; R-6…R-9)
- Source: fable-review 07, steal 7 — Fabro's numbered-requirements discipline (R1–R90 briefs, requirements traced into plan implementation units, rejected alternatives recorded with reasons). Roadmap 09, Phase 0.
- Today: `docs/product-briefs/*.md` are ad hoc (no template exists); `prd-template.md` has no requirements section; `plan-template.md` tasks don't cite requirements. The discipline is enforced here by template structure + `aet-plan` prose; mechanized checking (`aet plan validate`) is Phase 4, out of scope.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. Create `.agents/templates/brief-template.md`: Problem, Context, **Requirements** (R-1… numbered, each independently testable), Non-Requirements, **Rejected Alternatives** (each with a reason), Success Signal — S (traces: R-6)
2. Update `.agents/templates/prd-template.md`: add `## Requirements` (R-numbered; carried from the brief when one exists, minted here otherwise) between Non-Goals and User Stories; add one-line instructions that user stories and acceptance criteria cite the R-ids they satisfy — S (traces: R-7)
3. Update `.agents/templates/plan-template.md`: task-list line format becomes `Task description — size (traces: R-n)`; add `## Rejected Alternatives` section (what was considered, why not); add validation step "every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason"; add the lifecycle `status` field to the frontmatter example (`draft`/`approved`/`queued`/… per CONTEXT.md — gap found during scope validation) — S (traces: R-8, R-10)
4. Update `aet-plan/SKILL.md`: `create-prd` step 4 includes the R-numbered requirements section; `create-stories` step 6 adds R-id citation to each ticket; `plan` self-consistency lint gains **Check 4 — R-trace coverage**: an in-scope R-id with no covering task = FAIL; a task citing an unknown R-id = FAIL — M (traces: R-9)
5. Update `aet-pipeline-plan/SKILL.md`: one line in Step 1 noting that R-trace discipline is enforced by `aet-plan` and demonstrated at the P0 exit gate — S (traces: R-9)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] All template/prose changes for one discipline batched on one branch deliberately
- [x] Diff expected ~5 files / ~150–200 lines
- [x] Cannot share a branch with rdm-01 (independent concern)

## Rejected Alternatives

- **Add an R-trace lens to `aet-validate-scope` now** — rejected: duplicates what Phase 4's `aet plan validate` will mechanize; prose-level enforcement in `aet-plan` is sufficient until then (PRD Non-Goals).
- **Retrofit existing PRDs/plans** — rejected: the discipline applies forward; retrofitting 42 PRDs adds noise, no signal.

## Files to Modify

- `.agents/templates/brief-template.md` (new)
- `.agents/templates/prd-template.md`
- `.agents/templates/plan-template.md`
- `aet-plan/SKILL.md`
- `aet-pipeline-plan/SKILL.md`

## Validation Steps

- [ ] `make validate` passes
- [ ] Each of the three templates contains an R-numbered example (`grep -l "R-1" .agents/templates/*.md` → 3 files)
- [ ] `aet-plan/SKILL.md` lint section lists Check 4 (R-trace coverage)
- [ ] No source files introduced → no unit tests; named checks are `make validate` + the template greps above
- [ ] End-to-end demonstration deferred by design: the first post-merge planning cycle (expected: roadmap Phase 1) is the PRD's fourth acceptance criterion
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Templates are additive/structural; no downstream code parses them (the orchestrator reads plan frontmatter only, which is unchanged).

---

_Stage: reviewed_
_Next step: run `aet-sync-docs`_

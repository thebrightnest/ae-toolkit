---
id: wfd-03-engine-rewiring
size: M
blocked_by:
  - wfd-01-frontmatter-routing
  - wfd-02-workflow-schema-loader
pipeline: standard
status: approved
security_review: required
security_review_reason: rewires the orchestrator's gate sequencing source of truth
docs_sync: required
docs_sync_reason: deletes pipeline.py — docs referencing the stage table must reconcile
---

# Plan: Engine Consumers Load the Workflow; the Hardcoded Table Dies

## Context

- PRD: `docs/prds/roadmap-p1-workflow-as-data-prd.md` (G1; R-3, R-7, part of R-10)
- The extraction moment: with judgment dissolved (gate_key, from wfd-01) and the loader proven in parallel (workflow.py, from wfd-02 — both enforced via frontmatter `blocked_by`), the engine swaps its source of truth from the `STAGES` literal to `load_workflow(repo_root)`, and `aet-work/lib/pipeline.py` is deleted.
- Consumer inventory (ground truth at planning): orchestrator import `:41`; membership check `:566`; grouping `:578`; gate_key skip helper call sites (post-wfd-01); `CHECKING_SKILL_TO_VERDICT` + `verdict_kind_for_stage` `:307-325`; entry-stage literal `"plan-approved"` at `:150` and `:1450`; board-column map `aet-work/bin/review:22-30`. `aet-state` is stage-agnostic — untouched.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- The orchestrator calls `workflow.load_workflow(repo_root, workflow_name)` once per task and threads the `Workflow` object; `workflow_name` comes from the new plan frontmatter key `workflow:` (default `"software"`), read alongside the existing `pipeline:` isolation key (`workflow:` selects _which_ stage sequence; `pipeline:` selects _how_ its sessions are batched).
- Replacements: `STAGE_MAP` membership → `wf.stage_map`; `group_stages_by_session(isolation)` → `wf.session_groups(isolation)`; `verdict_kind_for_stage(stage)` → `stage.evidence` (delete `CHECKING_SKILL_TO_VERDICT` — the binding now lives in the workflow file); `"plan-approved"` entry literals → `wf.entry_stage`; terminal advancement → `wf.done_state`.
- `aet-work/lib/pipeline.py` is **deleted**; `tests/test_pipeline.py` is deleted with it after its parity assertions migrate into `tests/test_workflow.py` (they were written against the table in wfd-02; they now pin the packaged file as its own baseline — sequence, skills, evidence, groups stated literally in the test).
- `aet-work/bin/review`: the stage→board-column map keys on the loaded workflow — entry stage → `approved`, terminal skill-less stage → `queued`, anything else (including unknown vocabularies from variant workflows) → `in-progress`. Same rendered board for the software workflow as today.
- Failure mode: a missing or invalid workflow file fails the run loudly at task start (`WorkflowError` propagates with the resolution paths tried); no silent fallback to a baked-in sequence — the packaged default **is** the fallback.

## Rejected Alternatives

- Keep `pipeline.py` as a thin shim over `workflow.py` — rejected: two names for one concept invites drift; the roadmap language is explicit ("the hardcoded stage table in `pipeline.py` is deleted").
- Hardcoded emergency fallback sequence in the engine — rejected: that is the table again, wearing a trench coat; the packaged file is version-controlled and CI-linted.
- Deriving board columns from stage names in `bin/review` — rejected: name-matching is vocabulary lock-in; positional derivation (entry/terminal/other) works for any workflow.

## Task List

1. `aet-work/bin/orchestrator`: load workflow per task (`workflow:` frontmatter key, default `software`); replace membership, grouping, entry-stage, and terminal-advancement call sites; delete `CHECKING_SKILL_TO_VERDICT`/`verdict_kind_for_stage` in favor of `stage.evidence`; thread the `Workflow` object through `process_task`/`run_single`, adding any small accessors this needs to `aet-work/lib/workflow.py` — M (traces: R-3, R-7)
2. Delete `aet-work/lib/pipeline.py`; migrate the parity assertions from `tests/test_pipeline.py` into `tests/test_workflow.py` as literal baseline pins; delete `tests/test_pipeline.py` — S (traces: R-3, R-10)
3. `aet-work/bin/review`: positional board-column derivation from the loaded workflow with `in-progress` fallback for unknown stages; extend `tests/test_aet_work_add_review.py` for the fallback — S (traces: R-7)
4. Tests: extend `tests/test_orchestrator.py` — full traversal from the packaged file with patched `run_stage`/`run_stage_group` matching today's stage walk exactly; entry stage from data; verdict kind read from `stage.evidence`; loud failure on a broken repo-level workflow file — M (traces: R-10, R-3)
5. Merge branch to main and verify integration — S [Deferred: merges at closure via aet-ship, as noted in Validation Steps]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition — the highest-blast-radius change in the PRD, isolated deliberately
- [x] Diff expected > 3 files / > 50 lines
- [x] Cannot share a branch with the additive loader task; sequencing is enforced by `blocked_by`

## Files to Modify

- `aet-work/bin/orchestrator`
- `aet-work/lib/pipeline.py` (deleted)
- `aet-work/lib/workflow.py`
- `aet-work/bin/review`
- `tests/test_pipeline.py` (deleted)
- `tests/test_workflow.py`
- `tests/test_orchestrator.py`
- `tests/test_aet_work_add_review.py`

## Validation Steps

- [x] `make validate` passes
- [x] Named coverage: orchestrator rewiring → `tests/test_orchestrator.py` (integration: data-driven traversal parity, entry stage, evidence kinds, loud load failure); board projection → existing review coverage in `tests/test_aet_work_add_review.py` extended for unknown-stage fallback; migrated baseline pins → `tests/test_workflow.py`
- [x] `grep -rn "STAGES\|STAGE_MAP\|CHECKING_SKILL_TO_VERDICT" aet-work/` returns no hits
- [ ] Known docs divergence reconciled at the docs-sync stage: `docs/PIPELINE.md`'s stage table lists `tdd-complete` (never an engine stage) and mixes planning-footer values with engine stages — after this task it must point at the workflow file as the canonical stage list
- [x] `aet-work run-one` on a real queued task traverses identically to the pre-change engine — pinned machine-checkably by `TestWorkflowDrivenTraversal.test_full_traversal_from_packaged_file_matches_todays_walk` (exact group spans, skills, evidence kinds, final stage)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` (deferred to closure — task 5 merges after the review/secure stages)

## Rollback Plan

Revert the merge commit — `pipeline.py` and its table return intact; the workflow file and loader remain as unused additions. No queue or state migration in either direction.

---

_Stage: reviewed_
_Next step: run `aet-cso`_

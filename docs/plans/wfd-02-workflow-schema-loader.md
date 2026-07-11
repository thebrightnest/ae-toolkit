---
id: wfd-02-workflow-schema-loader
size: M
blocked_by:
  - rdm-01-decision-adrs
  - rdm-02-rtrace-templates
pipeline: standard
status: approved
security_review: required
security_review_reason: new engine-adjacent module that will drive gate sequencing
docs_sync: required
docs_sync_reason: introduces the workflow-file contract that docs must describe
---

# Plan: Workflow Schema, Packaged Default, and Loader

## Context

- PRD: `docs/prds/roadmap-p1-workflow-as-data-prd.md` (G1, G3; R-1, R-2, R-8, part of R-10)
- Doc 06 kernel/workflow/judgment split: stage sequence, skill bindings, evidence bindings are per-project **data**; `session_group` is execution policy, a separate axis from process definition; routing is config that must exist before adapters do.
- This plan is purely additive: the schema, the packaged default file, and the loader — no engine consumer changes (that is the follow-up rewiring task in this PRD). Parity is asserted against the still-existing `pipeline.py` constants, which pins behavior before the swap.
- Parallel-safe with `wfd-01` by construction: only new files.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

`aet-work/workflows/software.json` (packaged default, version 1):

```json
{
  "version": 1,
  "name": "software",
  "done_state": "done",
  "stages": [
    {
      "name": "plan-approved",
      "skills": ["aet-tdd", "aet-implement"],
      "evidence": null,
      "gate_key": null
    },
    {
      "name": "implemented",
      "skills": ["aet-qa"],
      "evidence": "qa",
      "gate_key": null
    },
    {
      "name": "qa-complete",
      "skills": ["aet-review"],
      "evidence": "review",
      "gate_key": null
    },
    {
      "name": "reviewed",
      "skills": ["aet-cso"],
      "evidence": "cso",
      "gate_key": "security_review"
    },
    {
      "name": "secure",
      "skills": ["aet-sync-docs"],
      "evidence": "sync-docs",
      "gate_key": "docs_sync"
    },
    { "name": "synced", "skills": [], "evidence": null, "gate_key": null }
  ],
  "execution_policy": {
    "session_groups": [
      ["plan-approved", "implemented"],
      ["qa-complete"],
      ["reviewed", "secure"]
    ]
  },
  "routing": {
    "default": { "harness": "claude", "model": null },
    "by_stage": {}
  }
}
```

- Succession is **list order** (linear only — DAGs are permanently fenced); the last stage advances to `done_state`. Entry stage = `stages[0].name`.
- `evidence` values must come from the fixed verdict menu (`evidence.SCHEMAS` keys); `null` for non-checking stages. This replaces the orchestrator's skill→verdict map at rewiring time.
- `execution_policy.session_groups` must partition exactly the skilled stages (skill-less terminal stages excluded). `minimal` = all skilled stages in one session; `full` = one session per skilled stage; `standard` = the groups as listed — semantics identical to `group_stages_by_session` today.
- `aet-work/lib/workflow.py` (stdlib-only): frozen dataclasses `WorkflowStage(name, skills, evidence, gate_key)`, `ExecutionPolicy(session_groups)`, `Routing(default, by_stage)`, `Workflow(version, name, done_state, stages, stage_map, execution_policy, routing)` with methods `entry_stage`, `next_stage(name)`, `session_groups(isolation)`. `load_workflow(repo_root, workflow_name="software")` resolves `<repo_root>/.agents/workflows/<name>.json` first, then the packaged `aet-work/workflows/<name>.json`; raises `WorkflowError` with a precise message on any structural violation (unknown evidence kind, duplicate stage, group referencing unknown stage, group containing a skill-less stage, bad routing shape, unsupported version).
- Terminology (scope validation): the schema field is `name`, never `class` — "work class" is reserved by `docs/PIPELINE.md` for the Trivial/Normal/Critical intake tiers, a different axis. Routing has no `by_class` sub-key: routing lives inside a per-workflow file, so the file's `default` **is** the per-workflow routing; `by_stage` is the only override axis.
- Unknown top-level and per-section keys are tolerated and preserved for forward compatibility (context-fidelity settings reserved) — tolerated by the **loader**; the stricter CI lint task in this PRD decides what merges.

## Rejected Alternatives

- YAML/TOML — rejected: JSON round-trips with the stdlib and matches the `.agents/*.json` ecosystem; `plan_parser`'s YAML subset stays minimal.
- Explicit `next` pointers per stage — rejected: list order already encodes the only legal shape (linear); explicit pointers invite DAG creep.
- Loading at module import time — rejected: resolution needs `repo_root` (the orchestrator serves any repo via `--repo-root`); loading is an explicit call.

## Task List

1. Write `aet-work/workflows/software.json` exactly as locked above — S (traces: R-1, R-2, R-8)
2. Write `aet-work/lib/workflow.py`: dataclasses, `load_workflow` with resolution order and strict validation, `session_groups(isolation)` reproducing today's minimal/standard/full semantics — M (traces: R-1, R-2, R-3, R-8)
3. Write `tests/test_workflow.py`: parity against `pipeline.STAGES` (sequence, per-stage skills, verdict kinds via the packaged file, session groups per isolation level), resolution-order override in a tmp repo, one failure test per validation rule, routing exposed on the object, unknown extension keys tolerated — M (traces: R-10, R-8, R-2)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not batched with the rewiring task deliberately: additive module first, engine swap second, each independently reviewable
- [x] Diff expected > 3 files-worth of lines (~300) though only 3 files
- [x] Cannot share a branch with the rewiring task without serializing the parallel-safe part of the batch

## Files to Modify

- `aet-work/workflows/software.json` (new)
- `aet-work/lib/workflow.py` (new)
- `tests/test_workflow.py` (new)

## Validation Steps

- [x] `make validate` passes
- [x] Named tests for each new source file: `aet-work/lib/workflow.py` → `tests/test_workflow.py` (unit: validation rules, resolution order; integration: parity with `pipeline.py` constants); `aet-work/workflows/software.json` → the same file's parity assertions
- [x] Parity check is exact: sequence, skills, evidence kinds, and groups all equal today's table
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` (deferred to closure — task 4 merges after the review/secure stages)

## Rollback Plan

Revert the merge commit — nothing consumes the new module yet; zero blast radius.

---

_Stage: implemented_
_Next step: run `aet-qa`_

# Reconciliation Report: FODS-06 Migration

**Plan:** `docs/plans/fods-06-migration-reconcile.md`
**Generated:** 2026-06-18
**Status:** pending human sign-off

## Summary

- Plans scanned: 97
- Plans already on frontmatter contract: 10
- Plans needing frontmatter: 87
- Recovered inter-plan edges: 43
- Plans with unresolved dependency lines: 41
- Plans flagged for human review: 5
- Terminal tasks identified for history backfill: 98

## Recovered dependencies

- `02-port-phases-0-2` → ['01-scaffold-skill-structure']
- `03-port-phases-3-4` → ['02-port-phases-0-2']
- `04-port-phase-5-preview` → ['03-port-phases-3-4']
- `05-integration-polish` → ['04-port-phase-5-preview']
- `abr-02-references-examples` → ['abr-01-scaffold-core']
- `abr-03-validate-package` → ['abr-02-references-examples']
- `aet-work-hybrid-orchestrator-docs-plan` → ['aet-work-hybrid-orchestrator-core-plan']
- `aet-work-state-refactor-derive-plan` → ['aet-work-state-refactor-status-next-plan']
- `aet-work-state-refactor-status-next-plan` → ['aet-work-state-refactor-derive-plan', 'aet-work-state-refactor-sync-init-plan']
- `aet-work-state-refactor-sync-init-plan` → ['aet-work-state-refactor-status-next-plan']
- `bs-02-pipeline-implement-merged-stage` → ['bs-01-aet-ship-merge-verification']
- `bs-03-aet-work-queue-tracking` → ['bs-02-pipeline-implement-merged-stage']
- `parallel-01-orchestrator-core` → ['parallel-02-skill-docs']
- `parallel-02-skill-docs` → ['parallel-01-orchestrator-core']
- `ph-01-plan-template-merge-step` → ['ph-02-work-queue-drift-detection']
- `ph-02-work-queue-drift-detection` → ['ph-03-aet-review-removal-safety']
- `qai-03-active-status` → ['qai-01-archive-cleanup']
- `rp-04-write-references-examples` → ['rp-03-write-skill-core']
- `rp-05-update-aet-ship-boundary` → ['rp-03-write-skill-core']
- `rp-06-write-adr` → ['rp-03-write-skill-core']
- `rp-07-validate-package` → ['rp-02-write-bash-script', 'rp-03-write-skill-core', 'rp-04-write-references-examples', 'rp-05-update-aet-ship-boundary', 'rp-06-write-adr']
- `ts-02-aet-pipeline-plan-guardrail` → ['ts-01-aet-plan-guardrail']
- `ts-03-aet-work-queue-validation` → ['ts-01-aet-plan-guardrail']
- `ts-04-aet-implement-runtime-enforcement` → ['ts-01-aet-plan-guardrail']
- `ts-05-conventions-docs` → ['ts-01-aet-plan-guardrail']
- `ts-06-package-validate` → ['ts-01-aet-plan-guardrail', 'ts-02-aet-pipeline-plan-guardrail', 'ts-03-aet-work-queue-validation', 'ts-04-aet-implement-runtime-enforcement', 'ts-05-conventions-docs']
- `ui-02-write-skill-core` → ['ui-01-scaffold-skill']
- `ui-03-write-examples-references` → ['ui-02-write-skill-core']
- `ui-04-integrate-validate` → ['ui-01-scaffold-skill', 'ui-02-write-skill-core', 'ui-03-write-examples-references']
- `waf-01-aet-work-queue-state` → ['waf-02-aet-work-worktree-hygiene']
- `waf-02-aet-work-worktree-hygiene` → ['waf-01-aet-work-queue-state']
- `wq-02-conventions-adr` → ['wq-01-skill-atomicity-updates']

## Unresolved dependency lines (human review required)

- `01-scaffold-skill-structure`
  - None — can start immediately.
- `abr-01-scaffold-core`
  - None — can start immediately.
- `abr-gate-01-fix-approval-gate`
  - None — can start immediately.
- `aet-ship-squash-merge-core-plan`
  - - Task 1 blocks Task 4 (work queue schema note references the detection logic)
  - - Tasks 2 and 3 are independent; run after Task 1 for clarity
- `aet-state-telemetry-foundation-plan`
  - - Task 1 (schema) blocks Task 2 (`aet-state`).
  - - Task 2 blocks Task 6 (tests for derive).
  - - Task 3 (telemetry) blocks Task 4 (`report`) and Task 6 (tests for telemetry).
  - - Task 5 (docs) can happen after Tasks 2-4.
- `aet-validate-scope-closure-discipline-plan`
  - - None.
- `aet-work-hybrid-orchestrator-core-plan`
  - None — this is the first slice.
- `aet-work-runtime-self-detection-plan`
  - - Task 1 blocks Task 2 (docs depend on the skill wording being final)
  - - Task 2 blocks Task 3 (validation runs on final state)
- `aet-work-state-refactor-derive-plan`
  - - None.
- `aet-work-state-refactor-sync-init-plan`
  - - None.
- `aet-work-yaml-fix-plan`
  - - None — all tasks are independent and can run sequentially.
- `bs-01-aet-ship-merge-verification`
  - None — can start immediately.
- `ccs-01-review-css-lens`
  - None — can start immediately.
- `ccs-02-template-framework-doc`
  - None — can start immediately. CCS-01 (review lens) is not a blocker; the ADR
  - references the CSS lens as the proven example, but the design is already
  - defined in the PRD.
- `cov-01-plan-validation-strategy`
  - None — this plan is self-contained.
- `cov-02-tdd-coverage-gate`
  - Task 3 references the file created in Task 4 — write Task 4 first (or in the same session). Task 5 (ADR) has no dependencies and can be written in any order.
- `cov-04-review-tests-lens`
  - Task 2 references the file created in Task 3 — write Task 3 first.
- `design-to-impl-hard-gate-systemic`
  - - Task 1 (audit) blocks Task 2 (aet-setup template)
  - - Task 2 (aet-setup) and Task 3 (skill-level gates) can run in parallel
  - - Task 4 depends on Task 2
  - - Task 5 depends on Tasks 2, 3, 4
  - - Task 6 depends on Task 5
- `em-01-foundation-adr-conventions-validator`
  - - None — this is the first plan in the sequence
- `extract-stack-plan`
  - - Task 1 blocks Tasks 2 and 3 (examples and references depend on the skill instructions).
  - - Task 4 depends on Task 1 (need the skill directory to exist before linking).
  - - Task 5 depends on Tasks 1–4.
- `mvr-01-remove-merge-verified-plan`
  - - Task 1 and Task 2 are independent; both must complete before Task 3.
  - - Task 3 depends on Task 1 and Task 2.
- `parallel-01-orchestrator-core`
  - - None — this is the first task in the parallel upgrade
- `ph-01-plan-template-merge-step`
  - - None — can start immediately
- `ph-02-work-queue-drift-detection`
  - - None — can start immediately
- `ph-03-aet-review-removal-safety`
  - - None — can start immediately
- `ph-04-aet-qa-orphaned-api-check`
  - - None — can start immediately
- `pipeline-plan-optional-ui-plan`
  - - Task 1–4 can be done in a single editing pass.
  - - Task 5 depends on Tasks 1–4.
- `pipeline-plan-remove-discover-plan`
  - - Tasks 1–6 can be done in a single editing pass.
  - - Task 7 depends on Tasks 1–6.
- `pp-01-validate-ui-integration`
  - - None (this is a self-contained skill edit).
  - - `aet-validate-ui` skill must exist (it does).
- `qai-01-archive-cleanup`
  - - None — this is the first task in the pipeline.
- `queue-append-fix-plan`
  - None — single task.
- `retro-stacked-pr-aet-ship-plan`
  - None — all three tasks are independent. Run 1 → 2 → 3 in order for clarity.
- `rp-01-scaffold-skill-structure`
  - None — can start immediately.
- `ts-01-aet-plan-guardrail`
  - - Task 1–4 can be done in a single editing pass.
  - - Task 5 depends on Tasks 1–4.
  - - No blockers — this is the root story.
- `ui-01-scaffold-skill`
  - None — this is the first task.
- `unified-orchestrator-plan`
  - - Task 1 blocks Task 2 (lib modules used by orchestrator)
  - - Task 2 blocks Task 3 (orchestrator must exist before updating skill docs)
  - - Task 3 blocks Task 4 (docs reference new behavior)
  - - Tasks 1-4 block Task 5 (tests cover implemented code)
  - - Tasks 1-5 block Task 6 (merge)
- `waf-01-aet-work-queue-state`
  - - None — can start immediately.
- `waf-03-aet-ship-branch-lifecycle`
  - - None — can start immediately.
- `waf-04-pipeline-implement-terminal`
  - - None — can start immediately.
- `waf-05-repo-hooks-deletion`
  - - None — can start immediately.
- `wq-01-skill-atomicity-updates`
  - - None — can start immediately

## Flagged plans (ambiguous references)

- `cov-03-qa-coverage-gate`: ['file reference `aet-qa/SKILL.md` is not a known plan']
- `rp-02-write-bash-script`: ["ambiguous whole-word ids: ['01-scaffold-skill-structure', 'rp-01-scaffold-skill-structure']"]
- `rp-03-write-skill-core`: ["ambiguous whole-word ids: ['01-scaffold-skill-structure', 'rp-01-scaffold-skill-structure']", 'file reference `SKILL.md` is not a known plan']
- `rp-04-write-references-examples`: ["ambiguous whole-word ids: ['01-scaffold-skill-structure', 'rp-01-scaffold-skill-structure']"]
- `rp-07-validate-package`: ["ambiguous whole-word ids: ['01-scaffold-skill-structure', 'rp-01-scaffold-skill-structure']"]

## Terminal tasks to backfill to `work-history.jsonl`

- `01-scaffold-skill-structure` (source: `work-queue.json`, status=merged, state=None, merge_commit=79ad754feaea6d5c19af4d6e25eb7818b2132305)
- `fods-02-state-spine` (source: `work-queue.json`, status=merged, state=None, merge_commit=0fdf8cca7a0c194619ada68abf8e1a9e7c376486)
- `fods-03-read-path-zero-git` (source: `work-queue.json`, status=merged, state=merged, merge_commit=401f6a0bf8e4960c418a0451bd0a95674a37d35d)
- `aet-design-system-creation-05` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `abr-02` (source: `work-archive.json`, status=merged, state=None, merge_commit=3043ba1cfbf120a8ddc153a9fd95c5aacbee95ab)
- `abr-03` (source: `work-archive.json`, status=merged, state=None, merge_commit=79cb2b24fccc14bed4a1f8d878663f3117f0910e)
- `abr-gate-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=5c96780e1609633df4b6f021bab1b020ff2f0ef7)
- `aet-ship-squash-merge-core-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=af88d7a)
- `aet-work-hybrid-orchestrator-docs` (source: `work-archive.json`, status=merged, state=None, merge_commit=eea3e13f3c2573e4c23ee8e54a32ac707056eb12)
- `aet-work-run-unification-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=None)
- `aet-work-runtime-self-detection-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=None)
- `aet-work-yaml-fix-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=541eccf6d4fedb938860f27013e6a4ccc8acf1a6)
- `bs-03` (source: `work-archive.json`, status=merged, state=None, merge_commit=964a9193af8d08270a6abddb907713cfc541e03c)
- `ccs-01-review-css-lens` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ccs-02-template-framework-doc` (source: `work-archive.json`, status=merged, state=None, merge_commit=None)
- `em-01-foundation-adr-conventions-validator` (source: `work-archive.json`, status=merged, state=None, merge_commit=311b34a5309010da23c8acd07a05f64ad799e2e0)
- `extract-stack-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=931daac26a4c8f4a6ae81b692ee40c2b615128b9)
- `parallel-02` (source: `work-archive.json`, status=merged, state=None, merge_commit=07c1cef)
- `ph-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=89c3277b7c7fb0469fd171cb8db320d3b57fd856)
- `ph-02` (source: `work-archive.json`, status=merged, state=None, merge_commit=9e8ce83532ab1742f80bdc5abbb378c892cfa13d)
- `ph-03` (source: `work-archive.json`, status=merged, state=None, merge_commit=6d3ee9b42e5b2202edeb93275cd2a0565ed752a9)
- `ph-04` (source: `work-archive.json`, status=merged, state=None, merge_commit=5fc39fe7652e78cf0148950331753b8732d59e2e)
- `pipeline-plan-optional-ui` (source: `work-archive.json`, status=merged, state=None, merge_commit=ed7046bba90cf5b7a9e69ad5b592ad085a812f21)
- `pipeline-plan-remove-discover` (source: `work-archive.json`, status=merged, state=None, merge_commit=095ac8e6f7e6939e90cf600e3d72d6d8608078ce)
- `planning-implementation-lockout-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=598ed7b6990e318d23c74d7a4de562f42487e378)
- `pp-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=df36fe99f9b213381a17a8115bbb89669d46e7dc)
- `queue-append-fix` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `readme-pipeline-visibility` (source: `work-archive.json`, status=merged, state=None, merge_commit=e8f9b79c649827637be68b861e2d34409dab2309)
- `retro-stacked-pr-aet-ship-plan` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ts-06-package-validate` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ui-04` (source: `work-archive.json`, status=merged, state=None, merge_commit=27b030308d1b70e7eadd27701830b2f89bdb53e0)
- `wq-02` (source: `work-archive.json`, status=merged, state=None, merge_commit=1dc9ea1)
- `waf-02-aet-work-worktree-hygiene` (source: `work-archive.json`, status=merged, state=None, merge_commit=9fce763)
- `waf-03-aet-ship-branch-lifecycle` (source: `work-archive.json`, status=merged, state=None, merge_commit=1ecc9eaa14c69e908e2635c25d1dc9c2e679a1e4)
- `waf-04-pipeline-implement-terminal` (source: `work-archive.json`, status=merged, state=None, merge_commit=a412793d916eaf557a0454f8f8fdc40920935391)
- `waf-05-repo-hooks-deletion` (source: `work-archive.json`, status=merged, state=None, merge_commit=84d3be01b881c1ab3a4c4b676bbe7a3bc7b20f4c)
- `rp-07` (source: `work-archive.json`, status=merged, state=None, merge_commit=72406c6bf822468e5a07169a706e31d2ebf4f62e)
- `cov-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=54515de)
- `cov-02` (source: `work-archive.json`, status=merged, state=None, merge_commit=30bab66)
- `cov-03` (source: `work-archive.json`, status=merged, state=None, merge_commit=e92a0f7)
- `cov-04` (source: `work-archive.json`, status=merged, state=None, merge_commit=fee5a01)
- `mvr-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=a5aafda)
- `qai-01-archive-cleanup` (source: `work-archive.json`, status=merged, state=None, merge_commit=9713961)
- `aet-design-system-creation-04` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `abr-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=cf96175f4c881848c177a27c5ddc530693f8d84f)
- `aet-work-hybrid-orchestrator-core` (source: `work-archive.json`, status=merged, state=None, merge_commit=2171252d63384b97b59a77c823dfa73a00ca582e)
- `bs-02` (source: `work-archive.json`, status=merged, state=None, merge_commit=cd4570ddbf28ebb7ec06ddaee670c5a1cc2df4f9)
- `design-to-impl-hard-gate-systemic` (source: `work-archive.json`, status=merged, state=None, merge_commit=af88d7a)
- `parallel-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=f295e7d)
- `ts-02-aet-pipeline-plan-guardrail` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ts-03-aet-work-queue-validation` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ts-04-aet-implement-runtime-enforcement` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ts-05-conventions-docs` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ui-03` (source: `work-archive.json`, status=merged, state=None, merge_commit=da6a99607759b0f4bda0949ca3ca2483b36f4c72)
- `wq-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=00d1817)
- `waf-01-aet-work-queue-state` (source: `work-archive.json`, status=merged, state=None, merge_commit=b7869b9)
- `rp-04` (source: `work-archive.json`, status=merged, state=None, merge_commit=72406c6bf822468e5a07169a706e31d2ebf4f62e)
- `rp-05` (source: `work-archive.json`, status=merged, state=None, merge_commit=72406c6bf822468e5a07169a706e31d2ebf4f62e)
- `rp-06` (source: `work-archive.json`, status=merged, state=None, merge_commit=72406c6bf822468e5a07169a706e31d2ebf4f62e)
- `aug-01-aet-upgrade-skill` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `clv-01-aet-verify-skill` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `clv-02-foundation-smoke-integration` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `lrt-01-aet-evolve-updates` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `lrt-02-cross-project-channel` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `pqg-01-plan-self-consistency` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `pqg-02-fold-validate-ui` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `sci-01-pipeline-doc-and-build-system` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `sci-02-validator-and-contradictions` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `smr-01-aet-state-helper` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `smr-02-derived-status-and-review` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `tfd-01-aet-prime-repurpose` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `tfd-02-routing-table-and-guards` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `unified-orchestrator-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=1576b0dbac8f4a469d39e368320921f75ecb0333)
- `aet-design-system-creation-03` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `bs-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=5e77f35970d6f646fc0d73c70b55ec58d961ac37)
- `ts-01-aet-plan-guardrail` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ui-02` (source: `work-archive.json`, status=merged, state=None, merge_commit=2c0212eca2c4124070c6370b18bd8d0d1df5231d)
- `rp-03` (source: `work-archive.json`, status=merged, state=None, merge_commit=72406c6bf822468e5a07169a706e31d2ebf4f62e)
- `qai-03-active-status` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `aet-design-system-creation-02` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ui-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=00cbddae5565450785c2cf8431593dd394e54d39)
- `rp-02` (source: `work-archive.json`, status=merged, state=None, merge_commit=72406c6bf822468e5a07169a706e31d2ebf4f62e)
- `aet-design-system-creation-01` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `rp-01` (source: `work-archive.json`, status=merged, state=None, merge_commit=72406c6bf822468e5a07169a706e31d2ebf4f62e)
- `aet-ship-squash-merge-core-plan` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ccs-01-review-css-lens` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `ccs-02-template-framework-doc` (source: `work-archive.json`, status=merged, state=None, merge_commit=None)
- `clv-01-aet-verify-skill` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `cov-03-qa-coverage-gate` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `retro-stacked-pr-aet-ship-plan` (source: `work-archive.json`, status=done, state=None, merge_commit=None)
- `aet-state-telemetry-foundation-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=a3232f5)
- `aet-validate-scope-closure-discipline-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=b5d0b0e7556e9519512d9e2521f4d1b17342b4c5)
- `aet-work-state-refactor-derive-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=275d4ca2334d8a106c72ab806fbf399e55ec407e)
- `aet-work-state-refactor-status-next-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=5937509a564542f0e2794ef830bbe5dbf14a1d11)
- `aet-work-state-refactor-sync-init-plan` (source: `work-archive.json`, status=merged, state=None, merge_commit=68f632240b1936612d96ea49b7628bb74755a81d)
- `fods-01-record-merge` (source: `work-archive.json`, status=merged, state=None, merge_commit=2ab940e45ad1dde45145428be6bf16fc33c07328)
- `2026-06-18-orchestrator-run-one-hardening` (source: `work-archive.json`, status=merged, state=merged, merge_commit=16a631f66d38bdf713db35f438b3f58805ee2f70)
- `run-one-queue-bookkeeping-plan` (source: `work-archive.json`, status=merged, state=merged, merge_commit=61de14d474a15a6b9f0c6662960269f0ff6173f2)

## Sign-off

The recovered DAG is **not trusted** until this report is approved, per ADR-011 Decision 9.
Approve by replacing the line below with your name and date:

- [ ] Approved by: **\*\*\*\***\_**\*\*\*\*** Date: **\*\*\*\***\_**\*\*\*\***

## Rollback

Revert the migration branch to restore prior `docs/plans/*.md` and `.agents/work-queue.json`.
The append-only `work-history.jsonl` is safe to leave.

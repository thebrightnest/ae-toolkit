# PRD: Pipeline Performance & Self-Evolution Telemetry

*Stage: scope-validated*
*Next step: run `aet-work` (single-plan or multi-task queue)*

## Overview

Upgrade the AE Toolkit's pipeline efficiency and self-measurement capabilities. Make the pipeline isolation mode a deliberate, size-driven convention (`minimal` for S plans, `standard` for M plans, `standard`/`full` for L plans) with a risk override for auth, data, API, and dependency changes. At the same time, upgrade the telemetry schema so the toolkit can measure its own performance honestly: record which stage actually ran, capture the planning phase upstream of the orchestrator, classify failures, snapshot plan frontmatter, and count retries. Ship a reusable analysis script so every user can replicate these measurements.

## Goals

- **G-1**: Reduce orchestration overhead for small plans without degrading quality.
- **G-2**: Keep staged QA/review/security gates for medium and large plans where they catch real defects.
- **G-3**: Make the pipeline-mode choice explicit, reproducible, and observable in telemetry.
- **G-4**: Upgrade telemetry to capture actual work performed, planning-phase cost, failure causes, plan context, and retry counts.
- **G-5**: Give every toolkit user a script to analyze their own pipeline stage costs and failure patterns.

## Non-Goals

- This PRD does not change the orchestrator to auto-switch modes based on `size`.
- It does not remove or weaken any existing gate (`aet-qa`, `aet-review`, `aet-cso`, `aet-sync-docs`).
- It does not address the run-scoped context handoff or validation-deduplication improvements identified in `docs/audits/2026-07-13-pipeline-flow-efficiency.md`; those remain separate follow-ups.
- It does not redesign the telemetry archive layout or retention policy.

## Requirements

- **R-1**: `docs/PIPELINE.md` documents the size-based advisory pipeline-mode defaults and the risk override rule.
- **R-2**: `.agents/templates/plan-template.md` defaults `pipeline` guidance to the size-based rule and explains when to override.
- **R-3**: `skills/aet-plan/SKILL.md` instructs plan authors to set `pipeline` using the size-based default plus risk override.
- **R-4**: `docs/adr/047-pipeline-mode-by-plan-size.md` records the structural decision and telemetry evidence.
- **R-5**: `scripts/analyze-pipeline-efficiency.py` reads `~/.aet/telemetry/{project}/` and prints per-stage time, token, and failure breakdowns.
- **R-6**: Stage telemetry records include the actual stage(s) that ran, a failure classification (nsr-01 taxonomy), a plan frontmatter snapshot (`size`, `pipeline`, `security_review`, `docs_sync`, `aet_version`), and an attempt counter.
- **R-7**: Planning-phase sessions (`aet-plan`, `aet-validate-scope`) emit telemetry records capturing duration, tokens, and outcome.

## User Stories

- As a toolkit user writing an S-sized plan, I want the plan template to already suggest `pipeline: minimal` so I do not pay session-split overhead for trivial work. (satisfies: R-2)
- As a toolkit user writing an M-sized API change, I want the skill instructions to remind me to override to `standard` even though the size says `standard`, because API changes are risky. (satisfies: R-3)
- As a toolkit maintainer analyzing pipeline efficiency, I want stage records to tell me exactly what work ran so I do not have to reverse-engineer the workflow. (satisfies: R-6)
- As a toolkit maintainer evaluating the value of planning, I want telemetry to include planning-phase sessions so I can compare planning cost against implementation cost. (satisfies: R-7)
- As a toolkit user, I want a reusable script to measure whether our pipeline changes actually reduce overhead across all users' telemetry. (satisfies: R-5)

## Acceptance Criteria

- [ ] `docs/PIPELINE.md` contains a "Pipeline Mode Selection" section with a size-to-mode table and risk override list. (satisfies: R-1)
- [ ] `.agents/templates/plan-template.md` frontmatter comment explains the size-based default and links to `docs/PIPELINE.md`. (satisfies: R-2)
- [ ] `skills/aet-plan/SKILL.md` frontmatter contract explains how to choose `pipeline` by size and risk. (satisfies: R-3)
- [ ] `docs/adr/047-pipeline-mode-by-plan-size.md` is accepted and referenced from the PRD/plans. (satisfies: R-4)
- [ ] `scripts/analyze-pipeline-efficiency.py` runs without errors against `~/.aet/telemetry/aiskills/` and produces the per-stage breakdown used in this PRD. (satisfies: R-5)
- [ ] Stage records in `src/aet/telemetry.py` include `actual_stages`, `failure_class`, `plan_snapshot`, and `attempt`. (satisfies: R-6)
- [ ] Planning skills (`aet-plan`, `aet-validate-scope`) write a `planning` telemetry record at session end. (satisfies: R-7)
- [ ] `make validate` passes after all changes. (satisfies: R-1, R-2, R-3, R-5, R-6, R-7)

## Technical Notes

- The telemetry script must correctly handle grouped stage sessions (`stages` field) by splitting time/tokens equally across the spanned stages and mapping the record's `stage` field back to the actual stage that ran.
- The `actual_stages` field should supersede the current reverse-lookup convention; existing records remain valid for historical analysis but new records must be self-describing.
- `failure_class` should reuse the nsr-01 taxonomy (`environment`, `flaky`, `design`, `timeout`, `canceled`) already used by the night-shift runtime.
- `plan_snapshot` is a shallow copy of selected frontmatter keys plus `aet_version` (from the git tag per ADR-043) taken at run time so later plan edits or toolkit upgrades do not falsify historical telemetry.
- `attempt` increments each time a task retries a stage within the same run; the first attempt is `1`.
- Planning telemetry can be emitted by the skills themselves into `.agents/telemetry/planning/{date}/{session-id}.json` or via a small helper in `src/aet/telemetry.py`; the exact mechanism is implementation choice.
- Documentation changes must stay within the existing ADR/CONVENTIONS/PIPELINE style and not exceed line-length or markdownlint rules.

## Open Questions

- Should the orchestrator emit a warning when an S plan uses `standard` or an M plan uses `minimal`? (Out of scope for this PRD; reserved for a later ADR if the convention proves stable.)
- Should `attempt` reset on each new run or persist across runs for the same task? (Default: per-run counter.)

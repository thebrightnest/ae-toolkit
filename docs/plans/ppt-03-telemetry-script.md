---
id: ppt-03-telemetry-script
size: S
status: approved
blocked_by: []
pipeline: minimal
security_review: required
security_review_reason: new analysis script, read-only against telemetry
docs_sync: required
docs_sync_reason: PRD footer must reflect script addition
---

# Plan: Pipeline Telemetry Analysis Script

## Context

Create `scripts/analyze-pipeline-efficiency.py` so any user can replicate the stage cost and failure analysis on their own `~/.aet/telemetry/{project}/` archive. See PRD: docs/prds/pipeline-performance-telemetry-prd.md

## Intake Triage

- [ ] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Write `scripts/analyze-pipeline-efficiency.py` that scans `~/.aet/telemetry/{project}/` for stage records, handles grouped sessions (`stages` field), and prints per-stage time, token, and failure breakdowns. — S (traces: R-5)
2. Add a short usage note to `docs/telemetry-guide.md` referencing the script. — S
3. Run the script against `~/.aet/telemetry/aiskills/` and verify output matches the analysis in this PRD. — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 100 expected diff lines
- **M**: ≤ 1 day human time / ≤ 200 expected diff lines
- **L**: > 1 day OR > 200 lines — re-evaluate against the full guardrail model; split only if a limit is actually exceeded

## Rejected Alternatives

- **Build a full dashboard** — rejected: out of scope; the existing `aet panel` already covers visualization. This is a lightweight CLI companion.

## Files to Modify

- `scripts/analyze-pipeline-efficiency.py` (new)
- `docs/telemetry-guide.md`

## Validation Steps

- [ ] `python3 scripts/analyze-pipeline-efficiency.py aiskills` runs without errors
- [ ] Output includes per-stage hours, tokens, and failure rates
- [ ] `make validate` passes

## Rollback Plan

Delete the new script and revert `docs/telemetry-guide.md`.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and
dependency changes should usually use `standard` or `full`.

---

*Stage: plan-approved*
*Next step: run `aet-work`*

---
id: readme-pipeline-visibility-plan
blocked_by: []
size: M
---

# Plan: README Pipeline Visibility Upgrade

## Summary

Add `aet-bug-report`, `aet-pipeline-plan`, and `aet-pipeline-implement` to README.md skill table, add pipeline callout to "What you get", and add pipeline invocation example to the "Run it" table.

## User Story

As a user discovering AE Toolkit, I want the README to accurately reflect all shipped skills and surface the pipeline entry points so I can choose the right workflow.

## Locked-In Decisions

- Keep pipeline skills in the main skill table (alphabetical sort), not a separate section
- Descriptions must stay under ~200 characters
- No changes to `docs/use-cases.md` in this ticket

## Files to Modify

- `README.md` — skill table, "What you get" bullets, "Run it" table

## Task List

1. **Add missing non-pipeline skills to main skill table**

   - Insert `aet-bug-report` in workflow-phase order (near review/QA)
   - Insert `aet-sync-docs` in workflow-phase order (near ship/evolve)
   - Ensure descriptions are concise and accurate

2. **Add "Pipelines" subsection below main table**

   - Create a new subsection header (e.g., `### Pipelines`)
   - Add `aet-pipeline-plan` with concise description and link
   - Add `aet-pipeline-implement` with concise description and link

3. **Add pipeline callout to "What you get"**

   - Add bullet: "One-command full flows — `aet-pipeline-plan` runs discover → plan → validate in sequence; `aet-pipeline-implement` runs tdd → implement → qa → review without manual skill switching"

4. **Add pipeline example to "Run it" section**

   - Add a prose sentence or dedicated row showing how to invoke pipelines per tool

5. **Self-validation**
   - Run `make validate`
   - Run `make package`
   - Verify README renders correctly (no broken table formatting)

## Self-Validation Strategy

- `make validate` — lint + format-check + skill-structure validator
- `make package` — regenerate `.skill` files
- Visual check: confirm table alignment and markdown rendering

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_

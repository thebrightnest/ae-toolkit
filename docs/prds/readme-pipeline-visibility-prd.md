# PRD: README Pipeline Visibility Upgrade

## Overview

The README.md is the primary discovery surface for the AE Toolkit. Three recently shipped skills — `aet-bug-report`, `aet-pipeline-plan`, and `aet-pipeline-implement` — are absent from the skill table, and the pipeline concept is underrepresented in the "What you get" section. This upgrade makes the README a complete and accurate index of all available skills while surfacing the one-command pipeline entry points.

## Goals

- Every shipped skill is discoverable from the README skill table
- Users understand that `/aet-pipeline-plan` and `/aet-pipeline-implement` exist as orchestrators
- The Quick Start / Run it section reflects real invocation patterns (including pipelines)

## Non-Goals

- Rewriting the README narrative or value proposition
- Adding new skills (only surfacing existing ones)
- Changing installation mechanics or packaging

## User Stories

- As a new user, I want to see all available skills in one table so I know what the toolkit covers.
- As a returning user, I want to discover the pipeline skills so I can run full flows with one command instead of invoking skills individually.
- As a developer who hit a bug, I want to see `aet-bug-report` listed so I know structured debugging is available.

## Acceptance Criteria

- [ ] `aet-bug-report` and `aet-sync-docs` are added to the main skill table in workflow-phase order
- [ ] A new "Pipelines" subsection is added below the main skill table, listing `aet-pipeline-plan` and `aet-pipeline-implement`
- [ ] The "What you get" section includes a bullet about one-command pipelines
- [ ] The "Run it" section includes a pipeline invocation example
- [ ] `make validate` passes after the change

## Technical Notes

- The skill table currently has 16 rows; this adds 3 rows for a total of 19
- `aet-pipeline-plan` and `aet-pipeline-implement` should be positioned logically — either alphabetically or grouped. Alphabetically is simplest and matches current convention
- Keep descriptions under ~200 characters so the table renders cleanly on narrow viewports

## Open Questions

- Should pipeline skills be called out in a separate subsection ("Pipelines") rather than mixed into the main table? **Decision: Option C — add a "Pipelines" subsection below the main table for `aet-pipeline-plan` and `aet-pipeline-implement`; add `aet-bug-report` and `aet-sync-docs` to the main table in workflow-phase order.**

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_

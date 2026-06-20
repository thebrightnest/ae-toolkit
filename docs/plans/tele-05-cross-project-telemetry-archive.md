---
id: tele-05-cross-project-telemetry-archive
size: M
blocked_by:
  - tele-01-enrich-telemetry-schema
---

# Plan: Cross-Project Telemetry Archive

## Context

- PRD: `docs/prds/aet-telemetry-learning-prd.md`
- Depends on: `tele-01-enrich-telemetry-schema`

Project-level telemetry logs are currently lost after `aet-ship`/cleanup. This plan adds an opt-in archive under `~/.aet/telemetry/` and a miner that turns archived runs into learning candidates for `aet-evolve`.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Task List

1. Ensure `learning_candidate_record` exists in `aet-work/lib/telemetry.py` (from `tele-01`) — S
2. Create `aet-evolve/bin/ingest-telemetry` — M
   - Read `.agents/execution.log.jsonl`, `.agents/work-history.jsonl`, and `/tmp/aet-reports/{task-id}/*.md`.
   - Copy them to `~/.aet/telemetry/{project-slug}/{date}-{run_id}/`.
   - Sanitize absolute repository paths; prepend `project_id`/`repo_slug` headers.
3. Create `aet-evolve/bin/mine-learnings` — M
   - Scan the archive for recurring patterns (dependency issues, repeated loops, stage failures, review noise).
   - Output a ranked markdown report.
   - With `--propose`, print suggested edits to skill files; never write them directly.
4. Update `aet-evolve/SKILL.md` with the new commands — M
5. Update `docs/CONVENTIONS.md` cross-project channel notes if needed — S
6. Run `make validate` — S

## Files to Modify

- `aet-work/lib/telemetry.py` (schema only, no logic change)
- `aet-evolve/bin/ingest-telemetry`
- `aet-evolve/bin/mine-learnings`
- `aet-evolve/SKILL.md`
- `docs/CONVENTIONS.md`

## Validation Steps

- [ ] `aet-evolve ingest-telemetry` creates an archive directory with sanitized paths.
- [ ] `aet-evolve mine-learnings` produces a ranked report without errors.
- [ ] `make validate` passes.
- [ ] Each new source file introduced by this plan has a named test or validation step covering it.
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Remove the new scripts and skill instruction updates; archived data can be left in place or deleted manually.

---

_Stage: reviewed_

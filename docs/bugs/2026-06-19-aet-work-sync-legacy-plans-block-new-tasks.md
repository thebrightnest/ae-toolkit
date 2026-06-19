# Bug Report: aet-work sync blocks new tasks because it re-validates legacy plans

## Metadata

- **Reported:** 2026-06-19T17:17:39Z
- **Severity:** high
- **Status:** resolved

## Symptoms

`python3 aet-work/bin/sync` failed with 80 errors of the form:

```
❌ 01-scaffold-skill-structure.md: legacy dependency section found; move blocked_by to frontmatter
❌ 02-port-phases-0-2.md: legacy dependency section found; move blocked_by to frontmatter
...
```

Because the entire intake validation failed, no new plan files could be appended to the queue. The user had to work around the failure by manually appending the six `tele-*` tasks to `.agents/work-queue.json`. At that point the repo already had 7 plan files on disk that were not represented in the queue.

## Reproduction Steps

1. Start from the repo after the fods-05/fods-06/fods-08 epics landed.
2. Ensure `docs/plans/*.md` contains plans that already have frontmatter `blocked_by` but still retain a legacy `## Blocked by` / `## Dependencies` prose section (80 of 103 plans did).
3. Run `python3 aet-work/bin/sync`.
4. Observe that sync exits with code 1 and reports every legacy plan as invalid, adding nothing to the queue.

## Root Cause

Two related issues in `aet-work/bin/sync` and `aet-work/lib/plan_parser.py`:

1. **Global validation on an append-only command.** The `sync` implementation called `intake_validation_errors(plan_files)` over the entire `docs/plans/*.md` corpus. The `aet-work` SKILL.md defines `sync` as append-only: it should only validate plan files that are actually candidates to be added (not already queued or settled). By validating every file, historical drift in already-queued plans blocked forward progress.

2. **Legacy dependency sections treated as fatal even when frontmatter is authoritative.** `plan_parser.has_legacy_dependency_section()` flagged any plan containing `## Blocked by` / `## Dependencies` as a fatal intake error. After fods-06, many plans had valid frontmatter `blocked_by` while still keeping the old prose section for human readability. The frontmatter is the source of truth, so these plans should not have been rejected.

The fods-06 migration added frontmatter to legacy plans but did not remove the prose dependency sections. fods-05 then introduced fail-closed intake validation. The combination meant `sync` could no longer process the existing corpus.

## Fix Summary

- `aet-work/lib/plan_parser.py`:

  - Added `has_explicit_frontmatter_blocked_by()` to detect when a plan has already declared `blocked_by` in YAML frontmatter.
  - `intake_validation_errors()` now only rejects a legacy dependency section when the plan has **not** explicitly declared `blocked_by` in frontmatter.
  - Added an optional `limit_to` parameter so callers can validate a subset of files while still parsing the full corpus for cross-plan blocker resolution and duplicate-id detection.
  - Refactored frontmatter fence extraction into `_frontmatter_body()` to avoid duplicating the fence-parsing logic.

- `aet-work/bin/sync`:

  - Computes the set of candidate plans (not already in the queue and not settled in history) and passes `limit_to=candidate_files` to `intake_validation_errors()`.
  - This makes `sync` truly append-only: already-queued plans are trusted, and only new candidates are validated.

- `tests/test_init_queue_sync.py`:

  - Added `test_sync_does_not_revalidate_existing_queued_plans`, which verifies that an already-queued plan with a legacy dependency section does not block a new valid plan from being appended.
  - Added `test_explicit_frontmatter_blocked_by_detection`, which directly covers the new helper.

- `aet-work/SKILL.md`:

  - Clarified the `sync` procedure to state that intake validation runs on candidate plans only.

- Regenerated `aet-work.skill` via `make package`.

## Regression Test

- `tests/test_init_queue_sync.py::TestFrontmatterIntake::test_sync_does_not_emit_task_with_empty_blocked_by_from_unparsed_section` — still passes; a new plan with an unparsed legacy section and no explicit frontmatter `blocked_by` is still rejected.
- `tests/test_init_queue_sync.py::TestSync::test_sync_does_not_revalidate_existing_queued_plans` — new test covering the resolved behavior.

## Validation

- [x] Reproduction steps no longer trigger the bug (`python3 aet-work/bin/sync` now succeeds and reports `0 drifted tasks`).
- [x] Existing test suite passes with no new failures (`142 passed`).
- [x] `make lint`, `make format-check`, and `scripts/validate-skills.sh` all pass.
- [x] `make package` regenerated `aet-work.skill` with the updated code.

## Lessons Learned

- **Pattern:** Append-only tooling must not hold new work hostage to historical data. A global validator reused by an append-only command created a forward-looking failure.
- **Prevention:** When designing a command that is documented as append-only or forward-only, scope validation to the candidate delta and explicitly trust existing state. Cross-corpus parsing can still happen for ID resolution, but error reporting should be limited to candidates.
- **Reference:** `aet-work/SKILL.md` `sync` procedure already described append-only behavior; the implementation was the mismatch. No ADR required, but this reinforces the forward-only state model documented in `docs/adr/011-forward-only-deterministic-work-state.md`.

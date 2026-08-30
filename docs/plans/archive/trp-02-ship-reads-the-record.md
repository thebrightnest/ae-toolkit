---
id: trp-02-ship-reads-the-record
size: M
work_class: critical
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: Changes the pre-merge gate's input resolution and the CLI contract of the command that merges to main.
docs_sync: required
docs_sync_reason: Removes the .md argument form documented in aet-ship/SKILL.md and docs/CLI.md.
---

# Plan: `aet ship` Resolves a Task Record, Not a File

## Context

- PRD: `docs/prds/the-record-is-the-plan-prd.md` (R-2, R-3, R-4, R-9)
- Decision: ADR-061 (the record is the plan after intake)
- Open bug: `docs/bugs/20260819-ship-plan-resolution-assumes-committed-plan.md`
- The correct pattern already exists: `aet_state.py:1253-1275` (`cmd_record_merge`)
  loads by id from the queue, falls back to sealed history, and is idempotent on
  a settled task. Its comment cites R-4 and R-19.

All five ship entry points call `plan_parser.resolve_plan_arg`
(`ship.py:329, 541, 799, 886, 1113`), a filesystem-only resolver
(`plan_parser.py:640-656`). Every consumer downstream of it wants a spec field,
not a file: `_work_class_from_plan` → `spec.frontmatter.work_class`;
`_unchecked_tasks` and `_plan_task_count` → `spec.tasks`; `_extract_prd_link` →
`spec.body`; `parse_frontmatter(...).get("id")` → `spec.frontmatter.id`;
`title_from_plan` → `spec.title`. Nothing passes the plan to a subprocess.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The underlying symptom is a filed defect; it arrives here because the fix
      is a model and CLI-contract decision, not a targeted patch — the
      structural-redirect rule, as with `osd-01`

## Task List

1. **Extract the task-record lookup** from `cmd_record_merge` into one shared
   helper — live queue first, then sealed `work-history.jsonl` — and point
   `aet_state` at it so there is one implementation, not two — M (traces: R-2)
2. **Resolve a task id to a record in all five ship entry points**, replacing
   `resolve_plan_arg`. Read spec fields structurally; delete `resolve_plan_arg`
   and its tests — M (traces: R-2, R-3)
3. **Refuse the `.md` path form** with a message naming `aet sprint add` as the
   entry point — S (traces: R-3)
4. **Report and exit 0 on a settled task**, naming the recorded merge commit,
   matching `record-merge`. This is a state precondition on one record, not a
   second resolution path — S (traces: R-4)
5. **Fail closed when no record carries a spec**, naming the task id. An absent
   spec is never an empty or default value (ADR-033 §3, ADR-059) — S (traces: R-9)
6. **Delete the complexity this strands**: `_task_id_from_plan` (`ship.py:103`,
   an id → path → stem → id round trip), `_scope_audit`'s plan-file exclusion
   (`ship.py:582`, dead post-R-19), and the dead `Plan: [name](path)` links in
   `_build_pr_body` and `_generate_changelog_entry` — M (traces: R-2)
7. **Regression test**: `aet ship gate <id>` succeeds when the record carries a
   spec and `docs/plans/<id>.md` does not exist — the condition existing tests
   construct away — S (traces: R-2, R-4)
8. Merge branch to main and verify integration — S

## Floor Check

- [ ] Expected diff is below the calibrated floor threshold
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

Zero boxes. Two subsystems (`ship`, `aet_state`), an architectural invariant
(post-intake reads come from the record), and a breaking CLI change.

## Rejected Alternatives

- **Fall back to the record when the file is absent** — rejected: this is the
  bug report's own suggested fix, and it preserves the two representations whose
  divergence is the defect. Also unsafe as written: sealed records carry a full
  spec, so a naive id lookup would render a plan for a settled task and walk it
  into a second merge.
- **Keep the `.md` form for off-board plans** — rejected: two entry points is the
  split this PRD removes. `aet sprint add` is the one way onto the board.
- **A ship-local wrapper duplicating the lookup** — rejected: `cmd_record_merge`
  already has it. A second copy is the defect one layer up.
- **Render a temporary plan file from the spec for ship to parse** — rejected:
  no ship consumer needs a file; rendering one re-serializes data the record
  holds structurally.

## Files to Modify

- `src/aet/cli/ship.py`
- `src/aet/cli/aet_state.py`
- `src/aet/plan_parser.py`
- `tests/` — ship gate/merge/open/split, record lookup
- `docs/CLI.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-2 (1,2,6,7), R-3 (2,3), R-4 (4,7), R-9 (5)
- [ ] `aet ship gate <id>` succeeds with no plan file on disk
- [ ] `aet ship merge <settled-id>` prints the merge commit and exits 0
- [ ] `grep -rn 'resolve_plan_arg' src/` returns no hits
- [ ] `aet ship <path>.md` is refused, naming `aet sprint add`
- [ ] New shared lookup helper is covered by a named unit test
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commits. Ship returns to filesystem resolution, which fails for every
post-R-19 task — today's behaviour.

## Pipeline

`standard`.

---

_Stage: plan-approved_

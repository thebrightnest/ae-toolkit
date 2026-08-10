---
id: t2r-12-plan-archival-at-closure
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: modifies the fail-closed closure transaction in src/aet/cli/aet_state.py — the canonical persisted-state writer (ADR-047 persisted-state risk override)
docs_sync: required
docs_sync_reason: implements PRD R-11; the PRD divergence summary must record the archival behavior
---

# Plan: Plan Archival at Terminal Closure

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-11). 173 settled plan
files sit in the live `docs/plans/` directory that `init-queue` scans (the
corpus that made the init-queue validation deadlock possible); a broad
footer/frontmatter grep today matches ~204 files, so the sweep detects
settled-ness from authority rather than a fixed count. Settled plans must
move to `docs/plans/archive/` at terminal closure, inside the slc-04
single-transaction closure (`_apply_transition`, `src/aet/cli/aet_state.py:374`;
footer-write leg at lines 503–531), not as a follow-up prose duty.

Relevant prior decisions:

- ADR-054 / ADR-055: the durable write for plan paths happens only at
  terminal closure; `docs/plans/` is outside the intake durability gate.
  `archive/` lives under `docs/plans/`, so existing path-prefix hygiene
  rules keep matching archived files unchanged.
- slc-04 / slc-05 (`docs/plans/slc-05-set-stage-gate-submit-atomicity.md`,
  merged): closure is one code-owned transaction (queue state, ledger `land`
  event, plan footer). This plan extends that same transaction; it must not
  add a second writer or a skill-documented move step.
- Ledger taxonomy (`src/aet/ledger.py:28`): kinds are `cut`, `stage`,
  `verdict`, `land`. There is no file-move kind and none is added — the
  archive destination rides in the existing `land` event payload built by
  `_land_digest` (`src/aet/cli/aet_state.py:534`).
- Scan collision check: every corpus scanner uses non-recursive
  `plans_dir.glob("*.md")` (`src/aet/plans_lint.py:32`,
  `src/aet/cli/gate.py:106`, `src/aet/cli/sprint.py:104`,
  `src/aet/cli/sync.py:57`, `src/aet/cli/plans.py:51`,
  `src/aet/plan_validate.py:389`), so a subdirectory is excluded from scans
  by construction; the work is pinning that expectation with tests, not
  changing scan code. `init-queue` iterates queue-represented plan files
  only (`src/aet/cli/init_queue.py:261-270`) and already skips settled
  plans via `_is_settled_from_authority`.
- Retry-path assumption: `cmd_record_merge`'s sealed-task retry
  (`src/aet/cli/aet_state.py:1157-1198`) resolves the plan via
  `_resolve_plan_for_closure` (`src/aet/cli/aet_state.py:111`). After
  archival the original path no longer exists in the checkout, so the
  resolver gains an `archive/` fallback instead of restoring the file to
  the live directory.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Extend `commit_and_push_plan_change` (`src/aet/queue.py:641`) with an
   optional archive destination: when set, `git mv` the plan into
   `docs/plans/archive/` and stage both paths so the footer update and the
   move land in the same single commit it already produces — S (traces: R-11)
2. Wire the move into the terminal leg of `_apply_transition`
   (`src/aet/cli/aet_state.py:503-531`): pass the archive destination for
   `merged`/`abandoned` closures, keep the fail-closed behavior (a failed
   move aborts closure the same way a failed footer push does today), and
   add `archived_to` to the `_land_digest` payload; extend
   `tests/state/test_aet_state.py` for the closure move and the task-3
   retry fallback — S (traces: R-11)
3. Add an `archive/` fallback to `_resolve_plan_for_closure`
   (`src/aet/cli/aet_state.py:111`) so `cmd_record_merge` retries resolve an
   already-archived plan instead of restoring it to the live directory — S
   (traces: R-11)
4. Pin the scan exclusion: update the `plans_lint` module docstring to
   state `archive/` is out of corpus, and extend
   `tests/plan/test_plans_lint.py` and
   `tests/queue/test_init_queue_scoped_validation.py` asserting
   `docs/plans/archive/*.md` is invisible to `aet plans lint` and to
   init-queue's scoped validation — S (traces: R-11)
5. One-time sweep: `git mv` every settled plan (terminal footer stage or
   terminal frontmatter `status`, per `_is_settled_from_authority`'s
   definition) from `docs/plans/` into `docs/plans/archive/` in one
   mechanical commit — S (traces: R-11)
6. Update the plans-layout docs: AGENTS.md (`aet plans lint` row and the
   `docs/plans/` intake line) and `docs/CONVENTIONS.md` docs-boundaries
   table to state settled plans live in `docs/plans/archive/` — S
   (traces: R-11)
7. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 1 day OR > 600 lines — re-evaluate against the full guardrail model; justify above 1500

### Floor Check

- [x] This stands alone: plan archival at closure is one behavior, distinct
  from every other t2r plan; no sibling plan touches the closure
  transaction.
- [x] The expected diff (~300 non-mechanical lines across src + tests +
  docs, plus the rename sweep) exceeds branch/PR/review overhead.
- [x] The work cannot share a branch/PR with related tasks: no other t2r
  plan modifies `aet_state.py`'s closure path, and bundling the 173-file
  sweep with any feature plan would bury the mechanical diff in review.

## Rejected Alternatives

- **Skill-prose move step in `aet-ship` after closure** — rejected: a
  follow-up prose duty is exactly the pattern R-11 exists to delete; the
  move must be part of the atomic closure transaction (slc-04).
- **Delete settled plans instead of archiving** — rejected: settled plans
  are the audit trail (footer breadcrumbs, R-trace digests in `land`
  payloads); archival preserves history while clearing the scan set.
- **New ledger event kind (`archive`)** — rejected: the taxonomy
  (`cut`/`stage`/`verdict`/`land`) already covers terminal closure via
  `land`; the archive destination is payload data on that event, not a new
  event class.
- **Reusable `aet plans archive-sweep` command** — rejected: out of scope
  for this plan; the closure move prevents recurrence, and the legacy
  corpus sweep is a one-time `git mv` commit (scripts/archive/ precedent is
  for repo-migration scripts, not needed here).
- **Update each settled task's `plan_file` pointer in the sealed history** —
  rejected: history is append-only; the `_resolve_plan_for_closure`
  archive fallback (task 3) resolves the moved file without rewriting
  sealed records.

## Files to Modify

- `src/aet/queue.py`
- `src/aet/cli/aet_state.py`
- `src/aet/plans_lint.py`
- `tests/state/test_aet_state.py`
- `tests/plan/test_plans_lint.py`
- `tests/queue/test_init_queue_scoped_validation.py`
- `docs/plans/*.md` → `docs/plans/archive/*.md` (one-time sweep)
- `AGENTS.md`
- `docs/CONVENTIONS.md`

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`make test`)
- [ ] `tests/state/test_aet_state.py` (extended) covers closure archival:
  a `merged` closure produces one commit containing the footer update and
  the move to `docs/plans/archive/` (integration, fixture repo); a failed
  move aborts closure fail-closed (unit); `cmd_record_merge` retry
  resolves the archived plan via the `archive/` fallback (unit)
- [ ] `tests/plan/test_plans_lint.py` (extended): a plan under
  `docs/plans/archive/` produces no lint violations and is excluded from
  the corpus (unit)
- [ ] `tests/queue/test_init_queue_scoped_validation.py` (extended):
  archived plans are not in init-queue's scan set (integration)
- [ ] No new source files are introduced; every change extends an existing
  file with named test coverage above (no API boundary tests — no
  frontend ↔ backend contract surface)
- [ ] After the sweep, `grep -l 'Stage: merged\|Stage: abandoned' docs/plans/*.md | wc -l` prints `0`
- [ ] `aet plans lint` and `aet status` pass with the archived corpus
- [ ] R-trace coverage: R-11 covered by tasks 1–6; no task cites an R-id
  outside R-11
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. The sweep commit is pure `git mv` renames; reverting
restores the live directory. Closure code reverts with the merge; plans
already archived by new closures can be moved back with `git mv` without
state corruption because no queue record depends on the archive path (the
resolver fallback treats both locations as valid).

## Pipeline

`standard` — modifies the fail-closed closure transaction in
`src/aet/cli/aet_state.py` (the canonical persisted-state writer), so
ADR-047's persisted-state override applies: size lifts to M and the
pipeline to `standard`.

---

*Stage: qa-complete*
*Next step: run `aet-work`*

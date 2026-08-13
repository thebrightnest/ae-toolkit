---
id: owb-05-board-is-open-work
size: M
work_class: critical
blocked_by:
  - owb-01-spec-travels-in-task-record
  - owb-04-plan-tooling-and-board-review
pipeline: full
security_review: required
docs_sync: required
---

# Plan: The Board Is Open Work; Delete the Settled-ness Derivation

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirements: R-7, R-8, R-9, R-10
- **Consolidated** from two plans at guardrail review: "the board is open work" and "`ready` is computed from what left the board" are two halves of one derivation, in the same two files.
- Closes the ADR-011 → 013 → 034 → 054 → 055 lineage

Settled-ness only needs deriving because `init-queue` and `queue sync` re-enumerate from `docs/plans/*.md`, a directory that never forgets. ADR-013 already defines the board as holding only open work; nothing implements it that way.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. **Enumerate the board as the set of open work.** No command re-derives it by scanning the plans directory — M (traces: R-7)
2. **Delete `init-queue`** and its plan-scan rebuild — S (traces: R-8)
3. **Delete `_is_settled_from_authority`** and every caller's settled-ness filter — M (traces: R-8)
4. **Demote `.agents/work-history.jsonl` to a measurement log**, keeping `metrics` and ADR-028's track record working — S (traces: R-8)
5. **Compute `ready`** from `blocked_by` plus what has left the board — M (traces: R-9)
6. **Refuse any external assertion of readiness**, including a hand-added label — S (traces: R-9)
7. **Satisfy blockers without a settled-history store**: a dependent becomes ready when its blocker leaves the board — M (traces: R-10)
8. **Prove equivalence**: the live set is identical before and after for every task in the corpus, and a blocker that closed before its dependent was added does not deadlock it — M (traces: R-7, R-8, R-10)
9. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: it is the deletion the PRD is built around.
- [x] Diff exceeds overhead: an enumeration change plus three deletions.
- [x] Cannot precede its blockers: the board must not depend on plan files.
- ⚠️ **Near the ceiling** after consolidation. If implementation trips two ceiling signals, split along the enumeration/readiness seam with `Split from: owb-05-board-is-open-work`.

## Rejected Alternatives

- **Keep a settled-ness filter as a safety net** — rejected: a filter implies the enumeration can contain finished work, which is the state this plan makes unrepresentable.
- **Move settled-ness to the ledger (ADR-055 as written)** — rejected: the ledger has no reader; transporting it serves nothing.

## Files to Modify

- `src/aet/cli/init_queue.py` (deleted)
- `src/aet/cli/sync.py`
- `src/aet/cli/aet_state.py`
- `src/aet/queue.py`
- `tests/queue/`, `tests/state/`

## Validation Steps

- [ ] `grep -rn "_is_settled_from_authority\|init_queue" src/` returns nothing
- [ ] The live set is unchanged for every corpus task
- [ ] `aet metrics` still reports from the history log
- [ ] A hand-set readiness label does not make a blocked task runnable
- [ ] A dependent becomes ready after its blocker closes, with the history log absent
- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert. The history log and plan footers are still written by earlier phases, so the previous derivation resumes intact.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/owb-05-board-is-open-work.md*

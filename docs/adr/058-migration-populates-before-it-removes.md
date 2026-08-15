---
subject: migration-sequencing
---

# A Migration Populates Its Target Before It Removes Its Source

## Status

Accepted (2026-08-15). Implements R-19 of `docs/prds/open-work-board-prd.md`, whose forward-only landing this ADR exists to prevent repeating.

## Context

R-19 moved a task's spec out of `docs/plans/<id>.md` and into the task record, so a task planned on one machine is executable on another. `b95538dd` implemented it and deleted 62 plan files in the same commit. The 11 records already on the board had been created before that commit and carried only `plan_file` — a path. Every live task therefore referenced a file that no longer existed, and the queue was unrunnable until `owb-15` backfilled the records from `b95538dd~1`.

Nothing in the code was wrong. The forward path was correct, the fail-closed plan resolution of ADR-054 did its job and halted loudly rather than guessing, and the deleted files were recoverable one commit back. What failed was ordering: the commit that introduced the target also removed the source, with no step in between that populated the target for the rows that already existed.

The gap was in the planning as much as the implementation. R-19 was written as a forward-looking requirement — "new records carry the spec" — and its plan carried no backfill task. A requirement phrased about future writes says nothing about existing rows, and a plan derived from it inherits the silence.

## Decision

1. **A migration lands in at least two commits.** The first populates the new target for every existing row. The second removes the old source. They are never the same commit, and the second is not written until the first is verified against real data.

2. **A requirement that changes where data lives implies a backfill task.** When a plan introduces a new field, record shape, or storage location that an existing corpus must also satisfy, the plan carries an explicit task to populate it for existing rows. Absence of that task is a planning defect, catchable at scope validation, not a detail deferred to implementation.

3. **The backfill reads from a reproducible source.** Recovery reads from version control — a named revision available in every clone — not from a machine-local copy. A machine-local copy is a legitimate human safety net and an illegitimate migration mechanism: it works for exactly one operator.

4. **A backfill is idempotent and tolerant.** Re-running it is a no-op. A row it cannot recover is named and skipped, not a crash: a migration that halts on the first unrecoverable row leaves the corpus half-migrated with no report of what remains.

5. **A standing test asserts the invariant over live data, not only over fixtures.** `tests/state/test_live_board_specs.py` fails when any live task record carries no spec. Fixture tests prove the migration works; a test against the real corpus proves it was run and stays run.

## Consequences

- A migration costs one extra commit and one extra review pass. That is the price of the corpus never being in a state where the source is gone and the target is empty.
- Rollback of the removal commit is independent of rollback of the population commit, so a bad removal can be reverted without discarding a correct backfill.
- Scope validation gains a question it can ask mechanically: does this plan change where data lives, and if so, where is its backfill task?
- Backfill code is retained rather than deleted after one use. It is the documented recovery path when a record appears from an older clone, and its cost is one small module.

## Alternatives Considered

- **Restore the deleted files and move on** — rejected: it unblocks in seconds and re-tracks exactly the files the requirement existed to untrack, walking the design backwards under time pressure.
- **Re-run intake for each affected row** — rejected: intake creates a fresh record, discarding transition history and resetting state, which for rows mid-flight is worse than the problem.
- **A prose warning in the planning skill** — rejected on the evidence of ADR-008, where a prose-declared hard gate proved to be declared-and-not-effective. The standing test in decision 5 is the enforcing half of this ADR; the prose is the explanation.
- **Dual-read forever (read the target, fall back to the source)** — rejected as a permanent state: the fallback is correct during migration and becomes a silent mask afterwards, hiding rows that were never populated. It is a transition mechanism with an expiry, not a design.

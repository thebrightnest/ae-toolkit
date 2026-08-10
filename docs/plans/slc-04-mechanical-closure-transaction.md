---
id: slc-04-mechanical-closure-transaction
size: M
work_class: critical
blocked_by:
  - slc-01-content-addressed-ledger-events
  - slc-03-frontmatter-status-removal
pipeline: standard
security_review: required
security_review_reason: rewrites the merge-closure path that records terminal state
docs_sync: required
docs_sync_reason: closure behavior is documented in aet-ship and the orchestrator prompt contract
---

# Plan: Mechanical Closure — One Code Transaction in `aet ship`

## Context

PRD: `docs/prds/single-ledger-closure-prd.md` (R-5, R-8). ADR-055. The
five-plan drift was invocation drift: `aet ship`'s closure is already
code-owned, but flows exist that never ran it, and the orchestrator
outsources the mid-pipeline footer write to an agent prompt
(`orchestrator.py:460`, `:1069`). This plan makes closure a single code
transaction every terminal flow routes through, records the permanent
digest event, and deletes the prompt duty.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. `aet ship` close executes one code transaction: footer breadcrumb update
   (via `update_plan_footer()`, `queue.py:602`), queue stage transition,
   and the terminal `land` event — no partial state on failure (refs
   updated via a single `git update-ref --stdin` transaction) — M
   (traces: R-5)
2. Route every terminal path through it: enumerate flows that reach
   `merged`/`abandoned` and remove any that write terminal state outside
   the transaction — M (traces: R-5)
3. Digest payload on the `land` event: plan content hash, PRD requirement
   ids, merge ref — so "what was the plan for this merge" is answerable
   from ledger + PRD + diff — S (traces: R-8)
4. Delete the prompt-delegated footer duty from the orchestrator prompt
   template (`:460`, `:1069`) and the "footer is only a breadcrumb"
   defensive comments it made necessary (`:1297`, `:1399`, `:3087`) — S
   (traces: R-5)
5. Kill-mid-transaction consistency test plus closure on a footer the
   agent never touched — S (traces: R-5)
6. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: closure atomicity is one observable behavior with its
  own failure modes (partial writes, unrouted flows).
- [x] Expected diff (~400 lines + tests) exceeds PR overhead.
- [x] Cannot share a branch with slc-05: slc-05 owns the *mid-pipeline*
  write path (`set-stage`, `gate submit`); this owns the *terminal* path.
  Sharing would couple two independently revertable behaviors.

## Rejected Alternatives

- **Harden the prompt duty instead of deleting it** (stronger wording, more
  validation) — rejected: the generative-cause finding; prose is a
  probabilistic executor, and the writer primitive already exists in code.
- **Delete the footer entirely** — rejected (review rev 6/7): it survives
  as a pure human breadcrumb precisely because code now maintains it for
  free.
- **Per-ref pushes for transactionality** — rejected: multi-ref atomicity
  comes from `git update-ref --stdin`, not from ordering pushes.

## Files to Modify

- `src/aet/cli/ship.py`
- `src/aet/cli/aet_state.py`
- `src/aet/queue.py`
- `src/aet/cli/orchestrator.py` (prompt template, breadcrumb comments)
- `skills/aet-ship/SKILL.md` (closure description)
- `tests/cli/test_ship_close.py` (new or extended)
- `tests/orchestrator/test_orchestrator.py` (prompt-template assertions)

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`make test`)
- [ ] `tests/cli/test_ship_close.py` covers the transaction: success path
  consistency (footer, queue, ledger agree), kill-mid-transaction leaves
  no partial refs, missing-plan refusal still fail-closed (lop-03
  regression) (integration)
- [ ] Orchestrator prompt contains no footer/status/queue mutation
  instruction (unit assertion on `build_prompt`)
- [ ] The `land` event carries plan hash, R-ids, and merge ref (unit)
- [ ] R-trace coverage: R-5, R-8 covered by tasks 1–5
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. Closure events already written to refs remain valid —
they are additive facts, and the pre-change code ignores them.

## Pipeline

`standard` — rewrites the terminal-state recording path (risk override per
ADR-047).

---

*Stage: reviewed*

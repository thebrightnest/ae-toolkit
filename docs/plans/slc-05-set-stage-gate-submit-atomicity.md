---
id: slc-05-set-stage-gate-submit-atomicity
size: M
work_class: normal
blocked_by:
  - slc-01-content-addressed-ledger-events
pipeline: standard
status: queued
security_review: required
security_review_reason: rewrites the verdict-ingestion path every gate depends on
docs_sync: required
docs_sync_reason: deletes documented prose procedures in four shipped skills
---

# Plan: `aet state set-stage` Footer Atomicity and `aet gate submit` Payload Builders

## Context

PRD: `docs/prds/single-ledger-closure-prd.md` (R-6, R-7). Prose-to-code
study §3.1.1/§3.1.2 (T1): `aet state set-stage` (`aet_state.py:1329`) writes
the queue stage but not the plan footer; four stage skills (aet-qa,
aet-review, aet-cso, aet-sync-docs) hand-construct verdict JSON, and
writer/reader path splits are the most repeated incident class in the log
(learnings 32, 37, 41, 43, 53). The writer primitives already exist — the
work is wiring and deleting prose.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. `aet state set-stage` writes the footer via `update_plan_footer()` in the
   same code path as the queue stage write (atomic pair); stale
   `failure_reason` cleared on reactivation
   (`aet-work/references/migration-aet-state.md:55` rule folds in) — S
   (traces: R-6)
2. The footer flip moves onto `aet gate submit`'s success path — "footer
   only after verdict" becomes structural; gate-ordering prose constraints
   in the four skills (aet-qa `SKILL.md:118-126`, aet-review `:102`,
   aet-cso `:104`, aet-sync-docs `:112`) are deleted — M (traces: R-6)
3. `aet gate submit` builds verdict payloads in code: `--from-pytest`,
   `--summary`, `--divergence`; the hand-constructed verdict-JSON fallback
   instructions in the four skills are deleted in the same change — M
   (traces: R-7)
4. Emit `stage` and `verdict` events to the ledger from these two paths —
   S (traces: R-6, R-7)
5. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: mid-pipeline write atomicity is one behavior, distinct
  from slc-04's terminal closure.
- [x] Expected diff (~450 lines across src + skills + tests) exceeds PR
  overhead.
- [x] Cannot share a branch with slc-04 (sequenced separation of
  mid-pipeline vs terminal write paths).

## Rejected Alternatives

- **Keep the skill-documented JSON fallback as an escape hatch** — rejected:
  the fallback is what the gate-rejection incidents pushed every stage
  onto; two sanctioned writers re-create the split (learnings:43).
- **A separate `aet footer write` command** — rejected: a footer write with
  no verdict is exactly the state the gate-ordering rule exists to prevent;
  the write must live on the verdict's success path.
- **Leave gate-ordering as documented prose** — rejected: four skills
  stating the same constraint is the prose-versus-prose drift pattern;
  structural beats documented.

## Files to Modify

- `src/aet/cli/aet_state.py`
- `src/aet/queue.py`
- `skills/aet-qa/SKILL.md`, `skills/aet-review/SKILL.md`,
  `skills/aet-cso/SKILL.md`, `skills/aet-sync-docs/SKILL.md`
- `skills/aet-work/references/migration-aet-state.md`
- `tests/cli/test_aet_state.py`, `tests/cli/test_gate_submit.py` (new or
  extended)

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`make test`)
- [ ] `tests/cli/test_gate_submit.py` covers the builders:
  `--from-pytest` produces a payload the gate accepts, including the
  tree_hash ordering shape learnings:43 rejected (unit + integration)
- [ ] A footer write is unreachable before its gate's verdict — no code
  path exposes it (structural test)
- [ ] `set-stage` mid-pipeline updates the footer with no agent action
  (integration)
- [ ] `grep -n "tree_hash\|verdict JSON" skills/aet-qa/SKILL.md
  skills/aet-review/SKILL.md skills/aet-cso/SKILL.md
  skills/aet-sync-docs/SKILL.md` shows no hand-construction instructions
- [ ] R-trace coverage: R-6, R-7 covered by tasks 1–4
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. Skill prose deletions restore with the revert; ledger
events already written remain valid additive facts.

## Pipeline

`standard` — rewrites the verdict-ingestion path (risk override per
ADR-047).

---

*Stage: reviewed*

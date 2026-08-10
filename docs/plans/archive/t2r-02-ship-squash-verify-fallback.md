---
id: t2r-02-ship-squash-verify-fallback
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: adds destructive remote/local branch deletion to the ship path
docs_sync: required
docs_sync_reason: deletes a shipped reference doc and rewrites an aet-ship example
---

# Plan: `aet ship verify --squash-fallback` and `aet ship close --delete-branch`

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-2 slice); prose-to-code
study §3.1.3 (`content/aet-structural-review/prose-to-code-study.md:105-107`).
ADR-055 (slc series): closure is a single code transaction in
`src/aet/cli/aet_state.py` (`cmd_record_merge`, :1126-1298) that already emits
the ledger `land` event and pushes the plan footer; `aet ship close`
(`src/aet/cli/ship.py:1229`) delegates to it. This plan is scoped against that
post-slc state and adds no prose writer around `aet gate submit` or
`aet state set-stage`.

Today the merge-resolution ladder already exists in code
(`resolve_merge_commit`, `aet_state.py:149-190`: ancestry → `gh pr view`
mergeCommit → exact diff-match via `resolve_by_diff`, :193-226), but the
operator-facing surface is still prose: the diff-match algorithm, its halt
conditions, and the record-then-force-delete choreography live only in
`skills/aet-ship/references/squash-merge-handling.md` (whole file) and
`skills/aet-ship/examples/squash-merge-example.md` (manual `gh` + `git branch
-D` steps). There is no `aet ship verify` command and no `--delete-branch`
flag; halt conditions are prose instructions ("HALT for manual verification"),
not exit codes.

Scope slice of R-2: this plan covers only the squash-merge diff-match
fallback, atomic record-then-delete, and named exit codes. The R-2 remainder —
stacked-PR detection with PR-body injection in `aet ship open`, `aet ship
split`, and trunk substitution inside commands — is deferred to a sibling
plan; it is a distinct command surface (`open`/`split` vs `verify`/`close`).

Collision check (PRD Technical Notes): `docs/plans/mvr-01-remove-merge-verified-plan.md`
(merged) removed the `merge_verified` queue field and its prose references; it
touched field semantics, not verification mechanics. Remaining `merge_verified`
mentions in `skills/aet-work/` are legacy-normalization notes only.
`docs/prds/merge-verified-redundancy-prd.md` (scope-validated) is fully
delivered by mvr-01 — no remainder collides with this slice. Outcome: no
collision.

Assumption recorded: the study's "N=20 threshold" originates in the prose
("check the last N commits … default N=20", squash-merge-handling.md:20). The
assignment calls it a line-drift threshold. This plan implements both: the
existing 20-commit search window is kept, and the tolerant match accepts a
candidate squash commit whose diff drifts from the branch diff by ≤ 20 lines
(covering the prose's known false-negative class — amended squash commits and
whitespace churn).

Ledger discipline: `verify` mutates no state, so it writes no event (the
taxonomy in `src/aet/ledger.py:28` — cut/stage/verdict/land — has no
verification kind and needs none). `--delete-branch` rides the existing
closure transaction, whose `land` event already records the merge ref and
strategy; branch deletion is a consequence of the landed record, not new
state.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. ✓ Line-drift tolerant diff-match in `src/aet/cli/aet_state.py`: extend
   `resolve_by_diff` (or add a sibling helper it delegates to) so that after
   the exact-match pass over the last 20 `origin/<target>` commits, a second
   pass accepts a candidate whose commit diff differs from the branch diff by
   ≤ 20 changed lines; return the match kind (`exact` | `drift`) alongside the
   SHA so callers can report it. Keep exact match preferred — drift match only
   fires when no exact match exists. Covered by new unit tests in
   `tests/ship/test_squash_fallback.py` — M (traces: R-2)
2. ✓ `aet ship verify <task_id|plan> [--squash-fallback]` in
   `src/aet/cli/ship.py`: runs the existing resolution ladder (ancestry →
   `gh pr view` mergeCommit → diff fallback from task 1), prints the resolved
   merge SHA, strategy, and match kind, and mutates nothing. Halt conditions
   from the deleted prose become named module-level exit-code constants:
   `EXIT_VERIFY_NO_MATCH` (no ancestry, no mergeCommit, no diff match —
   branch may be unmerged) and `EXIT_VERIFY_AMBIGUOUS` (empty branch diff, or
   more than one drift-match candidate). Covered by new integration tests in
   `tests/cli/test_ship_verify.py` — M (traces: R-2)
3. ✓ `aet ship close --delete-branch` in `src/aet/cli/ship.py`: run the existing
   `cmd_record_merge` closure first; only after it returns success (queue
   transition + ledger `land` event + footer push all landed) delete the
   remote branch (`git push origin --delete`) and the local branch
   (`git branch -D`, required because squash-merged commits are not
   ancestors). If closure fails, the branch is never touched — fail-closed —
   and the command exits `EXIT_DELETE_BEFORE_RECORD`. Honor `--dry-run` by
   printing the deletions that would follow a successful record. Covered by
   extending `tests/cli/test_ship_close.py` — M (traces: R-2)
4. ✓ Skill prose: delete `skills/aet-ship/references/squash-merge-handling.md`
   wholesale; rewrite `skills/aet-ship/examples/squash-merge-example.md` to
   drive `aet ship verify --squash-fallback` and `aet ship close
   --delete-branch` instead of manual `gh`/`git branch -D` choreography; in
   `skills/aet-ship/SKILL.md` replace the "Decision Procedure for Ambiguous
   Merge Verification" section with the exit-code table and add the two new
   commands to the Commands list — S (traces: R-2)
5. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 1 day OR > 600 lines — re-evaluate against the full guardrail model; justify above 1500

### Floor Check

- [x] Stands alone: squash-closure safety (`verify` + `close --delete-branch`)
  is one independently shippable behavior; the R-2 remainder (`open`/`split`)
  is a different command surface and ships separately.
- [x] Expected diff (~500 lines across src + tests + skill deletions)
  materially exceeds branch/PR/review overhead.
- [x] Cannot share a branch with the R-2 remainder plan: this slice deletes
  `squash-merge-handling.md`, which the sibling's stacked-PR work must not
  reintroduce; sequencing the deletion here keeps the sibling's diff clean.

## Rejected Alternatives

- **Keep `resolve_by_diff` exact-match-only as the whole fallback** — rejected:
  the prose itself lists amended squash commits as a known false-negative
  class; a fallback that fails on the exact case it exists for pushes
  operators back to the manual procedure.
- **Delete the branch inside `cmd_record_merge` (`aet_state.py`)** — rejected:
  the closure transaction owns queue/ledger/footer state; branch deletion is a
  ship-surface git side effect. Keeping record-then-delete orchestration in
  `ship.py` preserves the single-transaction invariant slc-05 established.
- **New ledger event kind for verification results** — rejected: `verify`
  mutates no state; the `land` event written by closure already carries the
  merge ref and strategy. Extending the taxonomy for a read-only command adds
  surface without signal.
- **Bundle stacked-PR detection and `aet ship split` into this plan** —
  rejected: different command surface (`open`/`split`), and bundling would
  push the plan past the 600-line M ceiling; deferred to the R-2 sibling.

## Files to Modify

- `src/aet/cli/aet_state.py`
- `src/aet/cli/ship.py`
- `skills/aet-ship/SKILL.md`
- `skills/aet-ship/references/squash-merge-handling.md` (delete)
- `skills/aet-ship/examples/squash-merge-example.md` (rewrite)
- `tests/ship/test_squash_fallback.py` (new)
- `tests/cli/test_ship_verify.py` (new)
- `tests/cli/test_ship_close.py` (extend)

## Validation Steps

- [ ] Lint passes (`make lint-py`); skill structure validator passes
  (`scripts/validate-skills.sh`) after the reference deletion
- [ ] Tests pass (`make test`)
- [ ] `tests/ship/test_squash_fallback.py` covers the tolerant matcher
  (unit): exact match preferred over drift; drift ≤ 20 lines accepted;
  drift > 20 lines rejected; search window capped at 20 commits
- [ ] `tests/cli/test_ship_verify.py` covers the command against a fixture
  git repo (integration): squash-merged branch resolves with strategy
  `squash` and correct match kind; unmerged branch exits
  `EXIT_VERIFY_NO_MATCH`; empty branch diff exits `EXIT_VERIFY_AMBIGUOUS`;
  no queue, ledger, or footer file is touched
- [ ] `tests/cli/test_ship_close.py` extended (integration): `--delete-branch`
  removes remote + local branch after a successful record; a failing
  record-merge leaves both branches intact and exits
  `EXIT_DELETE_BEFORE_RECORD`; `--dry-run` deletes nothing
- [ ] `grep -rn "branch -D\|merge-base --is-ancestor" skills/aet-ship/` shows
  no manual choreography remains outside the rewritten example's command
  output illustrations
- [ ] R-trace coverage: R-2 (this slice) covered by tasks 1–4; stacked-PR
  detection, `aet ship split`, and trunk substitution explicitly deferred to
  the sibling plan; no task cites an R-id outside R-2
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. The deleted prose reference restores with the revert;
ledger `land` events already written by closures that used `--delete-branch`
remain valid additive facts. Branches deleted by the new flag are recoverable
from the merge commit recorded in the queue (`git branch <task_id>
<merge_commit>`) if a deletion turns out to be premature.

## Pipeline

`standard` — modifies the merge-verification and closure path (risk override
per ADR-047 precedent from slc-05).

---

*Stage: merged*
*Next step: run `aet-ship`*

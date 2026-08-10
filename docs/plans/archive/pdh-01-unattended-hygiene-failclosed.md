---
id: pdh-01-unattended-hygiene-failclosed
size: M
blocked_by: []
pipeline: standard
status: merged
security_review: required
security_review_reason: Changes the execution-boundary contract — whether an unhygienic/non-durable working tree is allowed to spawn an unattended run — and extends ADR-005's "must still stop in unattended mode" category.
docs_sync: required
docs_sync_reason: The unattended-mode hygiene contract changes; ADR-005's relationship and any CONVENTIONS/AGENTS description of AFK behavior must reflect that main hygiene now halts unattended runs.
---

# Plan: Unattended `enforce_main_hygiene` Fails Closed on Durability Conditions

## Context

PRD: [plan-durability-hardening](../prds/plan-durability-hardening-prd.md) (R-1).
Root: `docs/bugs/2026-07-14-aet-add-queues-untracked-plans.md` (Gap 2).

`enforce_main_hygiene` (`aet-work/bin/orchestrator:192`) returns `True` with a
warning whenever `AET_EXECUTION_MODE=unattended`, so an AFK run proceeds on a
dirty/unpushed `main` and builds an empty worktree off `origin/main`. But
`check_main_hygiene` (`worktree.py:335`) is a **mechanical** durability check — and
ADR-005 already says mechanical hard-stops (merge-verification failures, critical
security, oversized) **must still stop in unattended mode**. This plan reclassifies
main hygiene into that category. The soften is safe to drop because
`check_main_hygiene` already excludes the queue file + `.lock`/`.lease` sidecars
(the original reason for softening), and no-remote projects don't trigger the
ahead-check.

## Intake Triage

- [x] Confirmed this is a **feature/hardening**, not a new reproducible defect (the defect is Gap 1, fixed)

## Locked Architecture Decisions

- In unattended mode, `enforce_main_hygiene` **fails closed** (returns `False`) on a
  real `check_main_hygiene` violation, rather than warn-and-continue. Interactive
  behavior is unchanged. Keep an explicit log line naming the halt reason.
- Scope of R-1: fail closed on **any** real hygiene violation (dirty non-sidecar
  tree or `main` ahead of `origin/main`) — per the approved PRD open-question, the
  simplest option, safe given the sidecar exclusion.
- Record the reclassification in **ADR-027** extending ADR-005 (ADRs are immutable;
  extend, don't edit 005).

## Task List

1. ✓ `aet-work/bin/orchestrator` — in `enforce_main_hygiene`, remove the unattended warn-and-continue branch so a `check_main_hygiene` failure returns `False` (halts) in unattended mode too; keep a clear halt log line — M (traces: R-1)
2. ✓ Author `docs/adr/027-main-hygiene-halts-unattended.md` (extends ADR-005: main hygiene is a mechanical durability hard-stop like merge verification, not a bypassable approval gate) and add its row to `docs/adr/README.md` — S (traces: R-1) [Added: README index also gained the missing ADR-024/025 rows — both ADRs existed on `main` unindexed]
3. ✓ Tests in `tests/test_orchestrator.py` — `enforce_main_hygiene` under unattended: main-ahead → halts; genuinely-dirty tree → halts; clean tree → proceeds; no-remote (no `origin/main`) → not falsely halted; interactive unchanged — M (traces: R-1)
4. Verify (see Validation Steps) and merge — S (traces: R-1) [Verify done 2026-07-14; merge at `aet-ship`]

[Added: `aet-work/references/queue-commands.md` updated to the fail-closed contract per this plan's `docs_sync` frontmatter; not in the original Files to Modify.]

**Size labels:** 4 files (orchestrator, ADR-027, adr/README, test), ~120 diff lines → **M**.

## Batching Check

- [x] Not near-identical additions
- [x] Diff > 3 files / 50 lines
- [x] Distinct file set from pdh-02 (skill docs)

## Rejected Alternatives

- **Surgical per-plan `origin/main` presence check** instead of general main hygiene — rejected: more code; the general check already covers the failure once the sidecar exclusion is accounted for.
- **Edit ADR-005 in place** — rejected: ADRs are immutable once accepted; extend with ADR-027.
- **Keep the soften, only warn louder** — rejected: warning is exactly what lets plans go missing in AFK runs.

## Files to Modify

- `aet-work/bin/orchestrator`
- `docs/adr/027-main-hygiene-halts-unattended.md` (new)
- `docs/adr/README.md`
- `tests/test_orchestrator.py`

## Validation Steps

- [x] Lint passes (ruff); `make validate` green
- [x] `tests/test_orchestrator.py` covers: unattended main-ahead halts · unattended dirty halts · unattended clean proceeds · no-remote not halted · interactive unchanged
- [x] **New source behavior** in `enforce_main_hygiene` is covered by the named `tests/test_orchestrator.py` cases above (unit-level, monkeypatching `AET_EXECUTION_MODE` and `check_main_hygiene`/a temp git repo)
- [x] ADR-027 exists (Status: Accepted), extends ADR-005, and is indexed in `docs/adr/README.md`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

**Self-consistency lint:** Check 1 PASS · Check 2 (orchestrator=t1, ADR+README=t2, test=t3) PASS · Check 3 (observable: halt vs proceed + exit codes) PASS · Check 4 (R-1 covered) PASS.

## Rollback Plan

`git revert` the commit; `enforce_main_hygiene` returns to warn-and-continue in unattended mode. No data migration.

## Pipeline

`standard` — execution-boundary behavior change with a new ADR and tests.

---

_Stage: merged_
_Next step: run `aet-ship`_

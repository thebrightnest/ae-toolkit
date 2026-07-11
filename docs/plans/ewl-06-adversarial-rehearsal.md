---
id: ewl-06-adversarial-rehearsal
size: S
blocked_by:
  - cli-03-skills-lint
  - ewl-03-hooks-install-pre-push
  - ewl-05-git-refs-tamper-evidence
pipeline: standard
security_review: skipped
security_review_reason: produces a rehearsal transcript and audit doc only; no source code changes to review beyond what ewl-03 and ewl-05 already covered under their own security reviews
docs_sync: skipped
docs_sync_reason: the audit doc is itself the documentation output of this plan; there is no separate maintained doc surface to reconcile against it
---

# Plan: Enforcement-Walls Adversarial Rehearsal

## Context

- PRD: `docs/prds/roadmap-p3-enforcement-walls-prd.md` (G4; R-7, R-8)
- Phase 3's exit gate, per the roadmap: the walls are demonstrated under real attempted violations, not asserted. This plan is that demonstration, executed after both walls exist (`blocked_by: ewl-03` for the pre-push hook, `ewl-05` for git-refs tamper-evidence — real dependencies, not just phase-ordering).
- Precedent: frh-14's A/B-findings audit report established the format this plan follows — a written transcript of what was attempted and what the system actually did, not a claim.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (a verification/demonstration deliverable), not a reproducible defect

## Locked design

- Two rehearsals, each with a captured transcript of the actual command output:
  - **(a) Hook rehearsal**: on a task branch with a required gate stage deliberately left unrecorded, attempt `git push`. Expected: the `aet hooks install`-installed pre-push hook (ewl-03) refuses the push with a named error identifying the missing stage. Also confirm a branch-deletion push still short-circuits (waf-05 behavior preserved) and a branch with all required gates recorded pushes cleanly.
  - **(b) Ledger rehearsal**: hand-edit a git-refs task ref or the envelope blob (`refs/aet/meta/queue`) outside the CLI. Attempt a read via `aet state`/`aet status`. Expected: the tamper-evidence mechanism (ewl-05) surfaces a fail-closed integrity error on the mutating path, or a warning on the read-only path, per ewl-05's contract.
- Both transcripts, their pass/fail verdicts, and any gaps found are written to `docs/audits/2026-07-enforcement-walls-rehearsal.md`, matching frh-14's audit-report structure.

## Rejected Alternatives

- **Automate the rehearsal as a CI-gated test rather than a recorded manual/scripted transcript** — rejected for this plan: R-8's automated regression coverage already lives in ewl-03 (`test_hooks_install.py` + its manual validation step) and ewl-05 (`test_git_refs_tamper_evidence.py`); this plan's job is the phase-level demonstration-and-record, not a third copy of the same automated check. A future CI job could replay this transcript, but that's not required to close Phase 3's exit gate.

## Task List

1. Execute rehearsal (a): attempt to skip gates and push a task branch; confirm refusal; capture output — S (traces: R-7)
2. Execute rehearsal (b): hand-edit a git-refs ledger write; confirm detection on next read; capture output — S (traces: R-7)
3. Write `docs/audits/2026-07-enforcement-walls-rehearsal.md`: both transcripts, verdicts, gaps found (if any) — S (traces: R-7)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition to anything queued
- [x] Diff is a single new doc file — no code changes
- [x] Cannot start before ewl-03 and ewl-05 are merged — real functional dependency, not shared-branch batching

## Files to Modify

- `docs/audits/2026-07-enforcement-walls-rehearsal.md` (new)

## Validation Steps

- [ ] Rehearsal (a) executed against a real installed hook (not mocked) and its actual output captured verbatim in the audit doc
- [ ] Rehearsal (b) executed against a real git-refs backend instance (not mocked) and its actual output captured verbatim in the audit doc
- [ ] R-trace coverage: R-7 by tasks 1–3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — removes the audit doc. No code behavior to unwind; this plan produces no code.

## Pipeline

`pipeline: standard`.

---

_Stage: plan-draft_
_Next step: run `aet-validate-scope`_

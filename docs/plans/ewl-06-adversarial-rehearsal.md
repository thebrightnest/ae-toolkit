---
id: ewl-06-adversarial-rehearsal
size: S
blocked_by:
  - cli-03-skills-lint
  - ewl-03-hooks-install-pre-push
  - ewl-05-git-refs-tamper-evidence
  - ewl-07-non-invasive-config-root
  - frh-18-group-evidence-path-contract
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
- **Mode 1 arm (R-7c) added 2026-07-12, narrowed 2026-07-12** with the non-invasive scope: the walls must be shown to hold with the AET **config external** — resolved from `~/.aet/{slug}/config.json`, no AET config in the tracked tree, no `refs/aet/*` pushed — so non-invasiveness is demonstrated, not assumed. (Plans and PRDs are versioned project artifacts and _may_ appear under `docs/`; that is expected, not a violation — only AET config and refs must stay out.) This adds `blocked_by: ewl-07` (the external config root the arm needs). The rehearsal is also written to be **honest about the hook's scope**: the pre-push hook stops a single operator who has it installed and does not bypass it; a fresh clone without the hook or a `--no-verify` push is a Mode 2 / server-side concern (roadmap doc 09 Phase 6), out of scope here and recorded as such rather than papered over.
- Precedent: frh-14's A/B-findings audit report established the format this plan follows — a written transcript of what was attempted and what the system actually did, not a claim.
- Also carries a supplementary **write-back observation** (rehearsal (c)): the thp-04 learning recorded two stacked causes — the `AET_EVIDENCE_PATH` mismatch (fixed by frh-18) and a `_record_stage` write-back non-persistence under batch concurrency that frh-18 explicitly dismissed as unsupported by evidence (`queue_lock` held across the load-modify-save at `aet-state:354`). Rather than open speculative hardening scope or leave the learning-vs-frh-18 disagreement untested, this rehearsal observes the write-back under a real concurrent batch and records the result either way. This adds `frh-18-group-evidence-path-contract` to `blocked_by`: the observation is only meaningful once frh-18's path fix is in place, otherwise the path mismatch masks the write-back behavior. Decision recorded during Phase 3 scope validation (2026-07-12).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (a verification/demonstration deliverable), not a reproducible defect

## Locked design

- Four checks, each with a captured transcript of the actual command output:
  - **(a) Hook rehearsal**: on a task branch with a required gate stage deliberately left unrecorded, attempt `git push`. Expected: the `aet hooks install`-installed pre-push hook (ewl-03) refuses the push with a named error identifying the missing stage. Also confirm a branch-deletion push still short-circuits (waf-05 behavior preserved) and a branch with all required gates recorded pushes cleanly. **Scope, recorded honestly:** this demonstrates the wall for a single operator who has the hook installed and does not bypass it — a fresh clone without the hook or a `--no-verify` push is explicitly _not_ claimed to be stopped here; that is Mode 2 / server-side enforcement (roadmap doc 09 Phase 6).
  - **(b) Ledger rehearsal**: hand-edit a git-refs task ref or the envelope blob (`refs/aet/meta/queue`) outside the CLI. Attempt a read via `aet state`/`aet status`. Expected: the tamper-evidence mechanism (ewl-05) surfaces a fail-closed integrity error on the mutating path, or a warning on the read-only path, per ewl-05's contract.
  - **(c) Write-back observation** (supplementary — thp-04's second, disputed cause): run a concurrent-batch stage group of the thp-04 shape (e.g. a `[reviewed, secure]` group across sibling tasks), post-frh-18 so the path mismatch is already out of the way. Expected: every completed task's `_record_stage` write-back persists — no task stuck at `qa-complete` while its footer reads `synced`. This **observes, rather than fixes**, the write-back race frh-18 dismissed; it records evidence either way and is not tied to a PRD requirement.
  - **(d) Non-invasive (Mode 1) rehearsal** (R-7c): with the AET config external (`~/.aet/{slug}/config.json`, ewl-07) on a scratch repo, run a task through gates, then repeat the essence of (a) and (b) — the generated hook still refuses a task-branch push missing a required gate, and a hand-edited git-refs blob is still caught on next read — while confirming the tracked tree carries no AET _config_ and no `refs/aet/*` is pushed. (Plans/PRDs under `docs/` are expected versioned artifacts, not a violation.) Where the scratch repo has no remote, note that (a) is N/A and the orchestrator evidence gate (frh-11) is the operative wall, and record that instead.
- All four transcripts, their pass/fail verdicts, and any gaps found are written to `docs/audits/2026-07-enforcement-walls-rehearsal.md`, matching frh-14's audit-report structure.

## Rejected Alternatives

- **Automate the rehearsal as a CI-gated test rather than a recorded manual/scripted transcript** — rejected for this plan: R-8's automated regression coverage already lives in ewl-03 (`test_hooks_install.py` + its manual validation step) and ewl-05 (`test_git_refs_tamper_evidence.py`); this plan's job is the phase-level demonstration-and-record, not a third copy of the same automated check. A future CI job could replay this transcript, but that's not required to close Phase 3's exit gate.

## Task List

1. Execute rehearsal (a): attempt to skip gates and push a task branch; confirm refusal; capture output — S (traces: R-7)
2. Execute rehearsal (b): hand-edit a git-refs ledger write; confirm detection on next read; capture output — S (traces: R-7)
3. Execute observation (c): run a concurrent-batch stage group (thp-04 shape, post-frh-18); confirm `_record_stage` persists for every completed task — none stuck at `qa-complete` with a `synced` footer; capture output. Supplementary observation of the write-back-race hypothesis; intentionally untraced (not a PRD requirement) — S
4. Execute rehearsal (d): config-external run (ewl-07) on a scratch repo; confirm the hook still refuses a task-branch push missing a required gate and tamper-evidence still fires, and that the tracked tree carries no AET _config_ with no `refs/aet/*` pushed (or, no-remote, that frh-11's evidence gate is the operative wall); capture output — S (traces: R-7)
5. Write `docs/audits/2026-07-enforcement-walls-rehearsal.md`: all four transcripts, verdicts, gaps found (if any) — S (traces: R-7)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition to anything queued
- [x] Diff is a single new doc file — no code changes
- [x] Cannot start before ewl-03, ewl-05, and frh-18 are merged — real functional dependency (frh-18 for the write-back observation (c)), not shared-branch batching

## Files to Modify

- `docs/audits/2026-07-enforcement-walls-rehearsal.md` (new)

## Validation Steps

- [ ] Rehearsal (a) executed against a real installed hook (not mocked) and its actual output captured verbatim in the audit doc
- [ ] Rehearsal (b) executed against a real git-refs backend instance (not mocked) and its actual output captured verbatim in the audit doc
- [ ] Observation (c) executed against a real concurrent batch (not mocked), post-frh-18, and its actual output captured verbatim in the audit doc
- [ ] Rehearsal (d) executed in a real config-external checkout (not mocked), post-ewl-07, with the no-AET-config-in-tracked-tree / no-`refs/aet/*`-pushed confirmation (or the no-remote note) captured verbatim in the audit doc
- [ ] R-trace coverage: R-7 by tasks 1–2, 4, 5; task 3 is an intentional supplementary observation (thp-04 write-back hypothesis), not traced to a PRD requirement; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — removes the audit doc. No code behavior to unwind; this plan produces no code.

## Pipeline

`pipeline: standard`.

---

_Stage: reviewed_
_Next step: run `aet-ship`_

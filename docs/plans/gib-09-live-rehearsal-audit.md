---
id: gib-09-live-rehearsal-audit
size: S
blocked_by:
  - gib-07-backlog-add
  - gib-08-reconcile-command
pipeline: standard
status: draft
security_review: skipped
security_review_reason: a demonstration + write-up exercising the already-implemented, already-reviewed projection paths against a throwaway GitHub repo; it introduces no new runtime code path of its own (mirrors twe-07/nsr-07 exit-gate rehearsals).
docs_sync: skipped
docs_sync_reason: the deliverable is an audit document under `docs/audits/`; it records evidence rather than changing a user-facing contract.
---

# Plan: Live Rehearsal + Audit (Exit Gate)

## Context

- PRD: `docs/prds/github-issues-backlog-projection-prd.md` — the exit-gate demonstration.
- **Why live:** every projection path is unproven against a real `gh` — the `quarantined` label gap is exactly what "never executed" costs. Mocked tests cannot establish that `gh` behaves as assumed. Precedent: `twe-07`, `nsr-07` rehearsals with audit docs under `docs/audits/`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (verification task over shipped feature code)

## Locked design

Against a throwaway GitHub repo with the projection configured, drive the full workflow and record evidence:

- **(a)** `aet backlog add` a draft plan → issue created, labeled `aet:draft`, keyed by plan id.
- **(b)** approve (validate-scope → `aet:backlog`); `aet sprint add` → `status: queued`, computed `aet:ready` (or `aet:blocked` for a blocked plan).
- **(c)** run a transition → `aet:in-progress`; close → issue closed.
- **(d)** a `quarantined` task → `aet:quarantined` (the previously-unlabeled state).
- **(e)** hand-break the board (delete an issue, wrong label) → `reconcile` dry-run reports it, `--apply` heals it.
- **(f)** kill `gh` auth mid-flow → the state transition still succeeds with a warning (fail-open).
- **(g)** second clone pulls after promote → `aet run` selects the same task (versioned membership).

Write `docs/audits/2026-07-github-projection-rehearsal.md` with a verdict per arm and an R-trace, honest about anything that does not hold.

## Rejected Alternatives

- **Mocked end-to-end only** — rejected: the whole risk is real `gh` behavior; a mock cannot retire it.
- **Skip the fail-open and second-clone arms** — rejected: those are the two properties the scenarios turned on (factory never stops; sprint travels).

## Task List

1. Prepare throwaway repo + projection config; run arms (a)–(g), capturing output — S
2. Write the audit doc with per-arm verdict + R-trace; record any gap honestly — S (traces: R-10, R-11, R-15, R-16, R-17)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Single cohesive demonstration; correctly one plan

## Files to Modify

- `docs/audits/2026-07-github-projection-rehearsal.md` (new)

## Validation Steps

- [ ] `make lint` passes on the audit doc
- [ ] Every arm (a)–(g) has a recorded PASS/FAIL with evidence
- [ ] R-trace: R-10/R-11/R-15/R-16/R-17 demonstrated end to end; no unknown R-ids
- [ ] No named unit test (rehearsal task); the audit doc is the evidence artifact
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit (removes the audit doc). No runtime effect; throwaway repo is discarded.

## Pipeline

`pipeline: standard` — verification task; grouping is immaterial but standard is the default.

---

_Stage: qa-complete_
_Next step: run `aet-review`_

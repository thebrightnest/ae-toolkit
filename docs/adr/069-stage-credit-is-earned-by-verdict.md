---
subject: stage-credit
relates: [11, 20, 65]
---

# A Failed Session's Progress Is Credited by Verdict, Not Inferred

## Status

Accepted (2026-08-28). Applies ADR-011 (Work State Is Recorded Forward) to the
session-group failure path. Motivated by
`docs/bugs/20260828-group-stage-advance-is-all-or-nothing.md`.

## Context

A session group runs several pipeline stages in one agent session and records
its stage once, at the group boundary, after every evidence gate in the span has
passed. The record is reached only on a zero exit: a session that dies partway
returns before it, leaving the task record at the group's entry stage no matter
how many of the group's stages finished.

The retry is then prompted with a stage that contradicts the worktree. On
2026-08-27 an implement commit — 22 files, +1389/−222 — was already on the
branch when 21 subsequent attempts were each told `Current stage: plan-approved.
Target stage: implemented`, and each re-ran `aet-tdd → aet-implement` over
finished work. The same symptom, reached by two other mechanisms, was measured at
roughly $24 on 2026-08-12 (`aet-toolkit-defects.md` D2 and D3).

The tempting remedy is to credit a stage from the commits it left behind, which
is what the operator did by hand to recover the task. ADR-011 forbids that
shape: state is recorded forward from evidence and never re-derived from a
secondary signal. A commit proves that work happened, not that a stage finished,
and the difference is invisible at exactly the moment it matters — an
unattended shift, where a stage credited on partial work has its remainder
skipped and nobody is watching.

## Decision

**A stage is credited only by its own passing verdict. Everything else the
session left behind is communicated, not recorded.**

1. **Verdict credits.** On a non-zero group session, the stages in the group's
   span are credited in order while each one's schema-valid passing verdict
   exists. The first stage that cannot be credited stops the walk, and the
   record names the last stage actually proven complete.
2. **An evidence-less stage is never credited.** A stage with no evidence
   binding — `plan-approved`, whose artifact is commits — is not creditable by
   any signal available on the failure path.
3. **The branch state goes to the handoff note.** What is already committed, and
   which verdicts already exist, is appended to the run's handoff note. The
   retry's prompt already carries that note, so the next session is told what
   exists instead of the record claiming a stage it cannot prove.
4. **Crediting never spawns a session.** The failure path reads verdicts. Asking
   an agent to produce a missing verdict stays on the success path, where
   `_require_passing_verdict` owns it.

## Consequences

- **Easier:** a retry after a late group failure resumes at the last proven
  stage instead of re-running the group. A group of `[reviewed, secure, synced]`
  that dies in `sync-docs` no longer re-runs the security review.
- **Easier:** the recorded stage keeps meaning exactly what ADR-011 says it
  means — a stage that finished and proved it.
- **Harder:** an interrupted evidence-less stage still re-runs. That is the
  deliberate cost of not crediting partial work, and the handoff note is what
  makes the re-run cheap rather than blind.
- **Harder:** the handoff note becomes load-bearing for cost, not only for
  context. It is run-scoped by design, so a retry in a *later* run does not see
  it and the branch is then the only record.

## Alternatives Considered

**Credit an evidence-less stage from commits created during the session.** Fixes
the observed case mechanically and matches the manual recovery. Rejected: a
session that commits halfway through implement and then hits a provider limit
would be credited as complete, and the skipped remainder surfaces as a defect in
review or in production rather than as a failed stage. It also re-derives state
from a secondary signal, which is the pattern ADR-011 exists to end.

**Recompute the stage from git on requeue.** Same objection, and it has no
answer for a stage that legitimately produces no commit.

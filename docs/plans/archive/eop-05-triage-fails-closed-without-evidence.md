---
id: eop-05-triage-fails-closed-without-evidence
size: S
work_class: critical
blocked_by: []
pipeline: standard
security_review: skipped
security_review_reason: Narrows when an agent session is spawned and what it may decide; removes an authority rather than adding one.
docs_sync: required
docs_sync_reason: Changes when triage runs, which the night-shift failure-handling contract describes.
---

# Plan: Triage Does Not Decide on an Empty Evidence Set

## Context

PRD: docs/prds/evidence-over-proxy-prd.md
Decision: ADR-072 (A Proxy Is Not Evidence), decision 5 — no evidence is not a
decision. Relates to ADR-030 (night-shift failure handling).

`build_triage_prompt` (`src/aet/triage.py`) interpolates `stage`,
`failure_class`, `signature` and `tail` into a prompt with no floor on any of
them. All four may be empty and the prompt is still well formed, so the agent
answers from the class label alone.

The fail-closed default in `parse_triage_verdict` does not cover this: it
returns `None` — deferring to the deterministic classifier — only when the output
is *unparseable*. A confident, well-formed `requeue` reached on no evidence
parses fine and is honoured.

Observed in `run-20260822-015936-psnjfhsl` (2026-08-22). Task
`e40-07-corpus-backed-citation-gates` failed with exit 1 and was triaged with an
empty stage, an empty signature and a tail of dashes. The agent's recorded
reasoning was that "a failure class of 'environment' typically means … often
transient and retryable", and it requeued. It had nothing else to reason from.

The check belongs before the session is spawned. The agent is what has no
evidence, so it cannot be the thing that refuses.

## Intake Triage

- [x] Demonstrable defect, recorded in
      `content/backlog/debt-triage-decides-without-evidence.md`
- [x] Routed here because it changes when an autonomous decision may be taken at
      all, which is the rule the PRD's ADR states

## Task List

1. Define what a sufficient evidence set is for a triage decision — at minimum a
   non-empty failure tail or a signature — as a predicate beside the prompt
   builder — S (traces: R-6)
2. Skip spawning the triage session when the evidence set is insufficient, and
   take the deterministic classifier default for the failure class instead — S
   (traces: R-6)
3. Record the skip as its own outcome in the run's telemetry, so a batch that
   never triaged is distinguishable from one that triaged and requeued — S
   (traces: R-6, R-8)
4. Unit tests for the predicate and for the orchestrator branch: an empty
   evidence set takes the default and spawns nothing; a populated one still
   triages — S (traces: R-6)
5. Merge branch to main and verify integration — S

### Floor Check

- [x] The change is limited to one subsystem and maintains no architectural invariant
- [ ] Expected diff is below the calibrated floor threshold
- [ ] `Files to Modify` substantially overlaps a sibling it is ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

One box checked: the fail-closed principle is ADR-030's and unchanged; this
widens what counts as the failing-closed case.

## Rejected Alternatives

- **Instruct the agent in the prompt to answer "insufficient evidence"** —
  rejected: it spends a session to ask a question answerable before spawning, and
  it relies on the agent honouring an instruction in exactly the situation where
  it has nothing to reason from.
- **Treat an empty evidence set as `quarantine`** — rejected: quarantine needs
  human attention, and an empty tail is more often a capture failure than a
  design defect. The deterministic classifier default is the already-decided
  answer for "no information".
- **Fix the tail capture instead** — rejected as the whole fix: worth doing, but
  it makes the empty case rarer rather than safe, and the decision path would
  still fail open when it recurred.

## Files to Modify

- `src/aet/triage.py`
- `src/aet/cli/orchestrator.py`
- `tests/orchestrator/test_triage.py`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] No triage session is spawned for a failure carrying neither tail nor
      signature
- [ ] The deterministic default taken on a skip matches the class the classifier
      returns for the same failure
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Triage returns to deciding on whatever it is given, which is
the behaviour every measured run so far has had.

## Pipeline

`standard` — this changes an unattended failure-handling decision.

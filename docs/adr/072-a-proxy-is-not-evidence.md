---
subject: evidence-substitution
---

# A Proxy Is Not Evidence

## Status

Proposed (2026-08-29). Generalises ADR-064 (Merge Evidence Is Recorded, Not
Inferred from Ancestry), which applied this reasoning to a single transition.
Relates to ADR-011 (Forward-Only Deterministic Work State), ADR-019 (Structured
Gate Evidence) and ADR-030 (Night-Shift Failure Handling), each of which places
weight on a signal this record defines the standard for.

## Context

ADR-064 settled that a branch's ancestry is not evidence that it merged: a branch
created from the trunk tip and never committed to is an ancestor of its own base,
so it satisfies the same test a genuinely merged branch satisfies. The phrase it
used for the result — "positive evidence is manufactured out of the absence of
work" — names a defect class, but the record fixed one site and the reasoning was
never applied anywhere else.

Six more instances are live, and each was found independently, by a different
route, over roughly two months. In each, a decision reads a signal that is cheap
to obtain in place of the evidence the decision actually needs, and the two are
indistinguishable to the reading code:

| Decision | Proxy read | Evidence needed | Where |
| --- | --- | --- | --- |
| Is this run live? | a PID number is held | the holder is the process the run started | `queue.py`, `cli/status.py`, `cli/main.py` |
| Is the lease reclaimable? | the same PID check | the same | `queue.py` `check_lease` |
| Is this task in progress? | a branch exists | a session ran and left work | `cli/aet_state.py` `derive_status` |
| Did the gate pass on this? | `make validate` passed in the cwd | it passed on the tree being merged | `cli/ship.py` |
| Is this stage attested? | `summary` is a `str` | `summary` says something | `evidence.py` |
| Requeue or quarantine? | a failure-class label | a stage, signature, or tail | `triage.py` |
| Did the scan find nothing? | a bucket count of `0` | the bucket was scanned | `cli/mine_learnings.py`, `cli/retro.py` |
| Is the suite green? | `0 failed` | no red is being discounted | `tests/` |

Two were observed misbehaving on 2026-08-29 without anyone going looking. `aet
status` reported five runs from 2026-08-19 as active; two of the PIDs belonged to
`QuickLookUIService` and `chrome_crashpad_handler`, both started days after the
runs they were attributed to. On the same board, `ppa-01` was stored
`in_progress` with `aet state audit` deriving `ready`, no branch, and a stale
worktree.

What makes this a class rather than a list is the shared failure mode. In every
case the proxy is **positively correlated** with the fact and **cheaper to
obtain**, so it works during development and under test, and diverges only in the
conditions nobody constructs: a recycled PID, an abandoned branch, a merge from
the wrong checkout, an interrupted writer, an empty archive. The divergence is
then silent, because the proxy answers confidently. A defect of this shape does
not announce itself; it degrades into folklore — "that run is stuck", "the task
doesn't exist", "that test is just flaky".

The corollary that makes it self-sustaining: a test written by the same author,
in the same session, constructs its input in the shape the code expects, and
therefore reproduces the proxy rather than the evidence. Three separate tests in
this repository passed over three of the defects above for exactly this reason.

## Decision

**A decision that depends on a fact must read evidence of that fact, not a signal
that merely correlates with it.**

Concretely, for this codebase:

1. **Existence is not activity.** That an artifact exists — a branch, a worktree,
   a PID entry, a directory — is not evidence that the work it would have been
   created for happened, or is happening. Where a fact is about work, the check
   must reach the work: commits on the branch, a recorded session, a process
   identity that matches the record.

2. **Identity must be checked, not assumed.** Where a record names a resource by
   a reusable handle — a PID, a path, a branch name — the reader must confirm the
   resource is the one the record meant. Every run directory in this repository
   already stores `started` beside `pid`; the evidence was on disk and unread.

3. **A check must be about its subject.** A gate that validates the ambient
   checkout says nothing about a tree resolved from somewhere else. Where a
   command resolves its subject deliberately, its checks resolve the same
   subject.

4. **Well-formed is not attested.** Where a payload is the fail-closed arbiter of
   a decision (ADR-019), the fields that carry its substance are value-checked,
   not only type-checked. A placeholder that satisfies a type is not an
   attestation.

5. **No evidence is not a decision.** An autonomous decision taken on an empty
   evidence set is a guess wearing a verdict's shape. Where the evidence set is
   empty, the deterministic default applies and the decision is not delegated.

6. **Absence and zero are different results.** A count of zero from a scanned
   population and a count of zero from an unscanned one must not render
   identically, in a report or in a test gate. A reader deciding "nothing
   happened" must be able to tell that something was looked at.

**Standard of review.** A change that introduces a read of a proxy where evidence
is available is refusable at review by citing this record. A change that must use
a proxy — because the evidence is genuinely unavailable — states so at the call
site, and says what divergence it accepts.

**Standard of test.** A test that constructs its own input cannot establish that
a proxy and its evidence agree, because it produces them together. Conformance to
this record is demonstrated by a test that constructs the *divergent* case: the
recycled PID, the zero-commit branch, the placeholder payload, the empty archive.

## Consequences

**Easier.** The eighth instance is refusable at review with a citation rather than
an argument. The seven known instances get one contract instead of seven
independent judgments, and `aet state audit`'s discrepancy flag becomes readable
as a conformance signal rather than a curiosity.

**Harder, and deliberately so.** Evidence costs more than a proxy. Reading a
process start time is more work than `os.kill(pid, 0)`; gating in a resolved
worktree is more work than running in the cwd. Each is paid once, in a code path
that already exists, and none of the seven fixes adds a mechanism, a dependency,
or a stored artifact — a constraint this record sets deliberately, because the
tempting fix for a missing fact is to start writing one down.

**A cost this record accepts.** Rule 6 makes some output longer and some gates
noisier: a report that distinguishes unscanned from empty says more, and a suite
that names its tolerated reds admits to having them. That is the intended
trade — the alternative is output that reads clean by being unable to say
otherwise.

**What this record does not do.** It does not settle where evidence *lives*.
Whether a verdict is a fact about a tree or about a run, and whether verdicts and
the provenance ledger should replicate off the machine that wrote them, are open
questions tracked separately. This record governs whether a decision may act on a
substitute for evidence it can already reach, not the transport of evidence it
cannot.

## Alternatives Considered

1. **Fix the seven sites without a record.** Rejected: this is what happened
   after ADR-064, which fixed one site and left the reasoning unstated. Six more
   instances were then found one at a time, each read as an isolated bug. The
   cost of the class is not the individual fixes; it is that each one has to be
   rediscovered.

2. **State it as a lint rather than a decision.** Rejected: the general form is
   not mechanically detectable. `os.kill(pid, 0)` can be grepped; "this check is
   about a different tree than the merge" cannot. A reviewer with a citable rule
   is the enforcement this class admits. Narrow lints remain worth adding where a
   specific proxy has a specific spelling.

3. **Require positive evidence universally, with no proxy permitted.** Rejected
   as unimplementable: some facts have no reachable evidence at acceptable cost,
   and a rule that is impossible to satisfy is ignored rather than followed.
   Hence the stated-exception clause in the standard of review.

4. **Amend ADR-064 in place rather than adding a record.** Rejected: ADR-064 is a
   decision about the merge transition and is correct as written. Widening it to
   a general rule would change what a reader citing it for the merge case is
   citing.

5. **Treat this as test-quality guidance rather than an architectural decision.**
   Rejected: the tests reproduce the defect because the production reads are
   wrong, not the other way round. The standard of test above is a consequence of
   the decision, not a substitute for it.

# Bug Report: every `aet state` call force-fetches `refs/aet/*`, discarding task-record writes the orchestrator has not pushed

## Metadata

- **Reported:** 2026-08-28
- **Severity:** high (silently disables the per-task circuit breaker in shared posture)
- **Status:** fixed 2026-08-28

## Symptoms

A task requeues without limit while the per-task breaker, whose threshold is 3,
never trips. Reported from the consuming repository (`dhl-agentic-tot`, task
`pub-03`): 22 attempts, 21 `failed → ready` transitions, $23.77, and **one**
`failure_signatures` entry on the sealed record.

The batch parent's triage line names the tell:

```
   ❌ Stage group failed with exit code 1
   ⚠️  Triage for pub-03-… failed closed; using requeue (environment)
```

`environment` is the default `_finalize_task` uses when the signature list is
empty (`orchestrator.py:2947`). The run's telemetry records
`failure_class: flaky` for 21 of 24 stage sessions, all with `exit_code: 1`, so
the classifier ran and its verdict was countable breaker evidence every time.

## Reproduction Steps

Local, deterministic:

1. Create a repo with an `origin` remote **and an in-tree
   `.agents/aet-config.json`** — the config is what makes
   `resolve_posture` return `shared` (`backends/factory.py:150-160`), and shared
   posture is what makes pushes live.
2. Seed a task through the git-refs backend and `backend.push()` it, as the batch
   parent does before spawning a child (`orchestrator.py:3311-3321`).
3. Call `_record_failure_on_task(...)` — the child's write. It lands on the local
   ref and is **not** pushed.
4. Call `backend.fetch()`, or anything that shells out to `aet state`.

Observed: the local task ref is force-reset to origin's pre-attempt copy and the
signature count goes from 1 to 0.

```
ref 126394ec -> 3f26e00d   signatures 1 -> 0
```

With no in-tree config the posture is `shadow`, pushes are suppressed, origin
carries no `refs/aet/*`, the fetch has nothing to overwrite with, and the
signature survives. The defect is invisible in exactly the setup the test suite
uses.

## Root Cause

Two halves of the design disagree about who owns a task record.

`GitRefsBackend.fetch` (`backends/git_refs_backend.py:349-358`) fetches with a
forced refspec and says so:

```python
_AET_FETCH_REFSPEC = "+refs/aet/*:refs/aet/*"
```

The leading `+` makes every fetched ref a non-fast-forward reset. Its docstring
states the intent — "The fetched refs overwrite local ones in the backend
namespace" — which is coherent for a store whose only writer is `aet state`,
because `aet state` pushes after saving (`cli/aet_state.py:1120`, `:1151`).

The orchestrator is a second writer that does not push.
`_record_failure_on_task` (`orchestrator.py:2496-2504`) ends at `backend.save`,
and `_finalize_task`'s first act on a failure is `_mark_failed`
(`orchestrator.py:2913`), which shells out to `aet state transition` — whose
first act is `backend.fetch()` (`cli/aet_state.py:113`). The child's signature is
therefore overwritten before the parent that must read it ever gets to look.

The loss is not specific to `failure_signatures`. Any field written through the
orchestrator's direct `backend.save()` and not pushed is discarded the same way —
verified with `cost`:

```
cost written locally: {'tokens': 999, 'usd': 1.5}
cost after fetch:     None
```

`_write_task_cost` (`orchestrator.py:2702-2722`) and `_attach_delivered_size`
both write through that path.

## Why The Tests Miss It

`tests/orchestrator/test_nightshift_rehearsal.py` runs a real batch end to end
and asserts that a deterministically failing task is quarantined by the breaker,
which looks like coverage for this. It cannot catch this defect for two
independent reasons:

- its temp repo has no in-tree `.agents/aet-config.json`, so the posture is
  `shadow` and no push ever reaches origin (`:_setup_repo`);
- it patches `should_quarantine_task` to `threshold=1`
  (`test_nightshift_rehearsal.py:279-287`), so it asserts that **one** signature
  is read, never that signatures accumulate across attempts.

The unit tests assert the in-memory dict only
(`test_circuit_breaker.py:36-59`, `:184`).

## Consequences

In shared posture — any project with a committed AET config, which is the
recommended setup — the per-task breaker cannot count past one, and the
`failed → ready` triage loop has no upper bound. The cost is unbounded in
principle; it was $23.77 on one task here, with roughly $23 of that spent on
attempts that returned in under three seconds.

## Prior Art In The Same File

One site already carried this fix, with a comment naming the mechanism exactly
(`orchestrator.py:2368` before this change):

```python
backend.save(queue)
# Push the merge_commit ref immediately so that the aet-state transition
# below (which fetches origin first) does not overwrite our local write
# with a stale remote ref.
backend.push()
```

So the invariant was understood, written down, and applied to the one field whose
loss was noticed. The other seven writes were left as bare saves. A rule enforced
at one call site is a comment, not an invariant, which is the general lesson here.

## Fix

`_save_task_record(backend, queue)` (`orchestrator.py:207-237`) saves and
replicates in one call, and states the invariant and its reason once. Every
direct task-record write in the orchestrator now goes through it: the failure
signature (`:2539`), the gap analysis (`:665`), the integration-failure record
(`:2189`), the merge commit (`:2368`, which keeps its own one-line note),
delivered size (`:2864`), and the three cost roll-ups (`:2756`, `:3874`,
`:3902`).

A push failure is reported rather than swallowed, naming the consequence — the
next fetch discards the write. Shadow posture and a repo with no remote both
return success from `push()`, so neither is warned about. The two sites that
already saved under `queue_lock` and pushed outside it are unchanged: they are
correct, and routing them through the helper would move their push inside the
lock.

Routing these writes through `aet state` instead — making the single-writer rule
the fetch refspec assumes actually true — remains the better shape and is a
larger change: it needs CLI surface for each field. The helper makes the current
two-writer arrangement honest in the meantime.

Not addressed: `+refs/aet/*:refs/aet/*` still discards local state with no
diagnostic of its own. A fetch that resets a task ref whose local copy differs
from the remote copy has no way to say so, because blobs carry no ancestry — the
push-after-write invariant is the only available guard.

## Regression Test

`tests/orchestrator/test_task_record_replication.py` runs in **shared** posture
with a real origin, at the real breaker threshold. It asserts that a signature
survives the `failed` transition, that three attempts accumulate to three
entries and trip `should_quarantine_task`, and that a cost roll-up survives the
same transition. One test pins the fixture's posture, so a change that silently
flips it back to `shadow` fails loudly instead of making the other three
vacuous.

Verified red before the fix (`0 != 3` on the accumulation test) and green after.

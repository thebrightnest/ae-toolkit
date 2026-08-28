# Bug Report: concurrent task-ref writes lose a compare-and-swap under `--dist=loadgroup`

## Metadata

- **Reported:** 2026-08-28 (first recorded 2026-07-24)
- **Severity:** medium (a tolerated red in the gate is how a real red gets waved through)
- **Status:** open

## Symptoms

`tests/orchestrator/test_integration_serialization.py::TestBatchIntegrationSerialization::test_max_jobs_three_integration_steps_serialize`
fails intermittently under the parallel suite and passes in isolation:

```
AssertionError: 1 != 0
```

with, in the captured output:

```
⚠️  Could not transition task-1 to awaiting_merge: atomic ref update failed:
fatal: cannot lock ref 'refs/aet/tasks/task-1': is at 4976f2ea… but expected cd235ad0…
```

It was named "the known `--dist=loadgroup` parallelism flake" in
`docs/bugs/2026-07-24-aet-ship-merge-does-not-merge-branch.md:163` and has been
tolerated since. It fired again during the 2026-08-28 validation run, where it
was briefly mistaken for a clean gate: a failure everyone recognises is a failure
nobody reads.

## Reproduction Steps

Not reliably reproducible on demand. Observed under `make validate` (xdist,
`--dist=loadgroup`); 4 consecutive isolated runs of the file and 1 of the single
test all passed on 2026-08-28.

## Root Cause

Not established. What is now known, from the ref work of 2026-08-28:

`GitRefsBackend.save` writes each task ref with a compare-and-swap against
`self._loaded_shas[task_id]`, captured at its last `load()`
(`backends/git_refs_backend.py:284-334`), and raises `RuntimeError` when git
refuses the update. The test runs three tasks with `max_jobs=3`, so the batch
parent and three children write the same ref namespace concurrently, and the
parent's cached shas can be stale by the time it saves.

Two candidate mechanisms, both consistent with the message:

- a child updated `refs/aet/tasks/task-1` between the parent's `load()` and its
  `save()`, so the parent's expected sha is one generation behind;
- `aet state transition`, invoked as a subprocess, fetched and re-wrote the ref
  while the in-process backend held its own cached sha.

The 2026-08-28 push-after-write change (`_save_task_record`) makes every direct
orchestrator write replicate, which changes the timing of ref updates in this
test but is not implicated: the failure predates it by five weeks, and the test
passed 4/4 in isolation and in a second full `make validate` after that change.

## Consequences

The gate is not trustworthy as a binary signal, which is the real cost. A
tolerated intermittent red trains readers — human and agent — to skim
`N failed, M passed` and conclude "the known one", which is exactly what happened
on 2026-08-28 before the second run disambiguated it.

Whether the underlying race can affect a real batch is unknown and is the
question worth answering: if a concurrent `aet run` can lose a task-record write
to a CAS conflict, the same class of loss that
`docs/bugs/20260828-fetch-discards-unpushed-record-writes.md` fixed by
replication has a second route.

## Fix Direction

Answer the production question first: reproduce the conflict deliberately (two
processes, one task ref, interleaved load/save) and determine whether
`RuntimeError` from `save` can reach a real run, or whether it is confined to
the test's fixture topology.

Then either make the write path retry on a lost CAS — reload, re-apply the field,
re-save, which is safe because these writes are field-level and idempotent — or
serialize the contended writes under the existing `queue_lock`, which two sites
already do.

Until then the flake must not stay invisible: either mark it `xfail(strict=False)`
with this report as the reason, so a green run means green, or move it out of the
default gate. A known red inside a passing gate is worse than either.

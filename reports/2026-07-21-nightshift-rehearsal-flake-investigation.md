# Nightshift Rehearsal Flake — Investigation Handoff

*Date: 2026-07-21. Status: **hypothesis specified, not yet confirmed**. Picked up
mid-investigation; the decisive experiment has not been run.*

## The ask

`tests/orchestrator/test_nightshift_rehearsal.py::TestNightShiftExitGateRehearsal::test_mixed_queue_finishes_unattended`
fails intermittently. Find the cause, fix it, and then test whether
`--dist=loadgroup` can be removed from the `test` target — because loadgroup
costs roughly 60 seconds on every code-touching `make validate`.

## Why this matters more than it looks

This repo has **no CI** (ruled out on cost), so `make validate` is the only
safety net. Two consequences:

1. An intermittently red gate trains people to re-run on red, which is how a
   real failure gets waved through.
2. The gate's speed is paid by a human, synchronously, every time. The
   `--dist=loadgroup` workaround is the single largest cost in it.

## Established facts

Measured 2026-07-20/21 on a 12-core machine.

| Observation | Value |
| --- | --- |
| Failure rate, full suite (`-n auto`) | ~1 in 10 runs |
| Failure rate, file run serially | 0 in 6 runs |
| Full suite, `--dist=load` | 37.3s / 44.1s |
| Full suite, `--dist=loadgroup` | 100.1s / 99.9s |
| Files sharing `xdist_group("orchestrator")` | 9 |
| `tests/orchestrator/` share of total test CPU | ~51% (182s of 355s) |

The failing assertion is that `nightshift-healthy` reaches `awaiting_merge`.
When it fails, the other three assertions in the class still pass, so the shift
as a whole completes — only the healthy task is affected.

## The mechanism (specified, unconfirmed)

The stall watchdog in `src/aet/cli/orchestrator.py:706-756` works like this:

- `last_output` is updated **only** when a line is read from the child's stdout.
- A watchdog thread polls every 0.1s and computes
  `elapsed = time.monotonic() - last_output`.
- If `elapsed > stall_timeout`, it terminates the process group, sets
  `cause = "stall"`, and returns exit code `-9`.

So the watchdog measures **silence on stdout**, not lack of progress.

Now the healthy fixture, written by `_write_fake_claude` in the test file. Its
first action is a chain of git subprocesses, and it prints nothing until they
are all done:

1. Python interpreter startup
2. `git rev-list --count main..HEAD` — `capture_output=True`, so its output
   never reaches the parent
3. Write `fixture-done.txt`
4. `git add .` — silent on success
5. `git commit` — **first output the parent can see**

Steps 1-4 are a silent window. The rehearsal sets `stall_timeout=5`
(`_setup_repo`), against a **production default of 300** (`orchestrator.py:681`)
— a 60× compression made to keep the test fast.

**Hypothesis:** under 12-way parallel load, with several workers spawning git
concurrently, that silent window occasionally exceeds 5 seconds. The watchdog
then misclassifies the healthy task as a stall and kills it, so it never
reaches `awaiting_merge`.

This fits every observation: it explains why the failure is load-dependent,
why it never reproduces serially, why only the healthy task is affected, and
why it is intermittent rather than systematic.

## Confidence, stated honestly

- **Established:** the watchdog measures stdout silence; the fixture has a
  silent git window; the rehearsal compresses the threshold 60×; the failure is
  load-dependent.
- **Not established:** that a failing run actually shows the healthy task killed
  with failure class `TIMEOUT`. The failing run's task state was never captured
  — this is the gap the next session should close first.
- **Inferred, weakly:** that `--dist=loadgroup` was added to stabilize this
  specific flake. It appeared in the Makefile mid-session from another change;
  serializing the orchestrator group would reduce exactly the contention this
  hypothesis depends on. Treat as plausible, not given.

## Ruled out

- **Not caused by the `setUpClass` collapse.** The class was changed on
  2026-07-20 to run one shared batch instead of four identical ones (committed
  in `af0ef20`). That *reduces* the number of batch runs, so it cannot add
  flake opportunities, and the file passes 6/6 serially with the change in
  place. Worth knowing the file was recently restructured.
- **Not caused by the plan/PRD work.** The rehearsal builds its own temp repo
  and never reads `docs/plans/`.

## Next steps, in order

**Experiment A — confirm the mechanism.** Run the rehearsal with a
deliberately tiny `stall_timeout` (e.g. `0.5`) and inspect the healthy task's
final record. If the hypothesis holds, its state is not `awaiting_merge` and
its last `failure_signatures` entry carries class `TIMEOUT`. This turns a rare
flake into a deterministic one and costs a few minutes. Do this before writing
any fix.

**Experiment B — fix the fixture, not the threshold.** Make the healthy
fixture emit output around its git calls so it is never silent for long:

```python
print("fixture: checking commits", flush=True)
ahead = subprocess.run([...])
print("fixture: staging", flush=True)
```

This changes nothing about what the test asserts. Re-run Experiment A: with
heartbeats, the task should survive even at a tiny `stall_timeout`.

Prefer this over raising the rehearsal's `stall_timeout`, which lengthens the
test — the stall fixture's kill is what dominates its runtime — and would only
widen the race rather than remove it.

**Experiment C — try removing loadgroup.** With B in place, drop
`--dist=loadgroup` from the `test` target in the `Makefile` and run the full
suite at least 10 times. Success is 10/10 green at ~40s rather than ~100s. If
it still flakes, the group is guarding something else and the cost has to be
justified on its own terms — do not silently keep paying it.

## Repro harness

The working harness lived in a session scratchpad and is gone. It is quick to
rebuild: load the test module with `SourceFileLoader`, call its module-level
helpers (`_init_git_repo`, `_copy_fixtures`, `_write_rehearsal_workflow`,
`_write_fake_claude`, `_write_queue`, `_commit_repo_state`) to build a temp
repo, put the fake CLI first on `PATH`, then run `orchestrator.run_batch` in a
thread with an `argparse.Namespace` copied from `_setup_repo` but with
`stall_timeout` parameterized. Afterwards read the queue file and print
`state` plus `failure_signatures` for `nightshift-healthy`.

The only knob that matters is `stall_timeout`; everything else can be copied
verbatim from `_setup_repo`.

## Open questions

- **Is the 5s threshold the bug, or the fixture?** Production defaults to 300s,
  where a silent minute is a genuine stall. The rehearsal compressed it 60× for
  speed and thereby created a race against its own setup. Heartbeating the
  fixture is the narrow fix. The broader question — whether a real agent doing a
  slow local operation could be killed for going quiet — is a product question
  worth asking separately, but it is *not* what this flake demonstrates, since
  no production run uses a 5s threshold.
- **Does anything else depend on the `orchestrator` xdist group?** Nine files
  carry the marker. If some of them genuinely conflict when run concurrently,
  removing loadgroup will surface a different flake. Experiment C's 10 runs
  should be treated as a smoke test, not a proof.

## Related

- `docs/prds/prose-lint-decoupling-prd.md` — explicitly scopes the loadgroup
  question **out**, noting it as the larger speed lever tracked separately.
  This report is that separate track.
- `src/aet/change_scope.py` (branch `validate-doc-fast-path`, unmerged) — the
  prose-only fast path. Unrelated to the flake, but it is why validate timing
  was being measured when the flake surfaced.

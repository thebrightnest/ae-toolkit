# Bug Report: the test suite writes records into the real provenance ledger

## Metadata

- **Reported:** 2026-08-20
- **Severity:** high
- **Status:** fixed

## Symptoms

`.agents/ledger.jsonl` — the append-only provenance store — contains records for
tasks that do not exist, carrying pytest temporary paths:

```json
{"kind": "land", "task": "t1", "payload": {"archived_to":
  "/private/var/folders/.../pytest-869/test_abandon_records_terminal_0/plans-archive/t1.md"}}
```

Of 553 records, roughly 200 are test fixtures: `t1` (137 events), `t0`, `t2`,
`t3` (20 each), plus `demo` and `blocker`. They are indistinguishable from real
provenance to any consumer that queries the ledger by task.

## Reproduction Steps

1. Record the ledger length: `wc -l .agents/ledger.jsonl`
2. Run `pytest tests/state -q`
3. Record it again.

Observed: **+98 records**, deterministically. Per file:

| Test file | Records written |
| --- | --- |
| `tests/state/test_concurrent_state.py` | 91 |
| `tests/state/test_aet_state.py` | 5 |
| `tests/state/test_desk_actions.py` | 1 |
| `tests/state/test_quarantined_state.py` | 1 |

## Root Cause

`tests/conftest.py` isolates every other machine-local store with an autouse
fixture — `_isolate_telemetry_archive`, `_isolate_plans_archive`,
`_isolate_aet_bin_dir`. The provenance ledger is the one that was missed.

Ledger isolation was instead opt-in per test: three call sites in
`tests/state/test_aet_state.py` wrap their assertions in
`patch.dict("os.environ", {"AET_LEDGER_PATH": ...})`. Every other test touching
a closure path — `aet state close`, `record-merge`, the desk merge action —
resolves `resolve_ledger_path()` with no override, falls through to
`_resolve_ledger_repo_root()`, discovers the real repository, and appends.

The store's own contract is what makes this severe: the ledger is append-only by
design, and `ledger.py` states "Never hand-edit it." Records written by mistake
cannot be removed without rewriting a file whose entire invariant is that
nothing rewrites it.

## Fix

The defect has two legs. The first fix stopped 98 of 99 writes; the second leg
was found only by measuring again afterwards.

**Leg 1 — in-process writes.** Added `_isolate_ledger` to `tests/conftest.py`,
matching the three existing fixtures. It sets `AET_LEDGER_PATH` to a per-test tmp
dir **and** monkeypatches `ledger._resolve_ledger_repo_root`. The second half is
not redundant: `_isolate_telemetry_archive` documents the reason — several tests
run code in-process under `patch.dict(os.environ, ..., clear=True)`, which wipes
the env var, and without the module-level patch those calls fall back to git
discovery and find the real repository.

That module-level patch also made the resolver's own tests untestable, since they
drive `_resolve_ledger_repo_root` directly. The fixture is therefore opt-out via
`@pytest.mark.real_ledger_resolution`, registered in `pyproject.toml` and applied
to the six tests in `tests/ledger/test_ledger.py`.

**Leg 2 — the spawned child.**
`tests/gate/test_gate_submit.py::test_gate_submit_routed_through_aet_dispatcher`
builds an **explicit env dict** for `subprocess.run`, listing `PATH`,
`AET_EVIDENCE_PATH`, `AET_BIN_DIR` and `AET_TELEMETRY_ARCHIVE_DIR`. Neither half
of leg 1 can reach it: a monkeypatched module attribute does not cross a process
boundary, and an env var absent from that dict is not inherited. The child ran
with the repository as its cwd, discovered the real root, and appended a
`verdict` event.

Which variables it *did* isolate is the tell — exactly the two the conftest
already covered. The list was copied from what was known to be needed, and the
ledger was not on it because the conftest never had it. Opt-in isolation
propagates its own gaps into every test that imitates it.

Fixed by passing `AET_LEDGER_PATH` into that env dict.

Tests that set `AET_LEDGER_PATH` themselves continue to override the fixture.

## Regression Test

The reproduction is the regression test: a test run must leave
`.agents/ledger.jsonl` unchanged. Measured after both legs:

| Suite | Before | After |
| --- | --- | --- |
| `tests/state` | +98 | 0 (122 passed) |
| `tests/gate` | +1 | 0 (61 passed) |
| `tests/ledger` | 0 | 0 (27 passed) |

A dedicated assertion was not added, because any such test would itself need the
fixture under investigation to be disabled, and the suite-level delta is the
stronger check.

## Validation

- [x] Reproduction steps no longer trigger the bug (delta 0, was +98 and +1)
- [x] `tests/state`, `tests/gate`, `tests/ledger` pass with no new failures
- [x] The 5 resolver tests broken by leg 1's module patch are fixed by the marker
- [ ] Whole-suite run confirming delta 0 — in progress at time of writing

## Outstanding

The ~200 fixture records already in the ledger are **not** removed by this fix.
Removing them means rewriting an append-only store, which contradicts its
invariant; `ledger.py`'s repair hint offers only "restore from a backup, or
remove it and accept the loss of provenance for events already recorded". That
is a deliberate decision to take separately, now that new writes have stopped.

## Lessons Learned

- **Pattern:** a conftest that isolates three of four machine-local stores is
  more dangerous than one that isolates none — the three set an expectation of
  isolation that the fourth silently breaks. This is the third instance of the
  same family found on 2026-08-20, after a merge mock creating `abc123def456/`
  in the cwd and a ledger root resolver trusting a stubbed `git rev-parse`.
- **Prevention:** when a module resolves a path to a real, shared location,
  isolating it belongs in the shared conftest, never in the tests that happen to
  remember. Opt-in isolation is a defect waiting on the next test author, and it
  spreads: the spawning test's hand-built env dict isolated exactly the stores
  the conftest already covered.
- **Measure again after fixing.** The first fix stopped 98 of 99 writes and
  looked complete. Only re-measuring the whole suite surfaced the spawned child,
  which no amount of in-process patching could have reached.
- **Reference:** `tests/conftest.py`; `src/aet/ledger.py` `resolve_ledger_path`.

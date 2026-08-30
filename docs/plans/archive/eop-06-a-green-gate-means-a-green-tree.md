---
id: eop-06-a-green-gate-means-a-green-tree
size: S
work_class: normal
blocked_by: []
pipeline: standard
security_review: skipped
security_review_reason: Test-suite markers and the removal of a script nothing invokes; no runtime behaviour changes.
docs_sync: skipped
docs_sync_reason: No documented contract changes; the removed script is named only in a fixture and a retired-path list.
---

# Plan: A Green Gate Means a Green Tree

## Context

PRD: docs/prds/evidence-over-proxy-prd.md
Decision: ADR-072 (A Proxy Is Not Evidence), decision 6 — absence and zero are
different results.

`tests/` contains **zero** `xfail` or `skip` markers, yet three intermittent
failures are known and tolerated:

| Test | Measured | State |
| --- | --- | --- |
| `tests/orchestrator/test_integration_serialization.py` `test_max_jobs_three_integration_steps_serialize` | fails under `--dist=loadgroup`, passes in isolation | cause not established since 2026-07-24 |
| `tests/orchestrator/test_nightshift_rehearsal.py` `test_stall_killed_and_classified_timeout` | 13–27% across 30 runs in August; 0/45 on 2026-08-24 | unreproducible |
| `tests/test_aet_run_dispatch.py` `TestRunOneBlocks` | seen once under `-n auto` | not investigated |

Because nothing distinguishes a known red from a new one, a reader recognises the
count and concludes "the known one". That happened on 2026-08-28: a flake was
briefly taken for a clean gate, and a second full run was needed to
disambiguate. The loadgroup report prescribes the remedy itself — mark it
`xfail(strict=False)` with the report as the reason, or move it out of the
default gate — and neither was done.

Two dead artifacts belong with this. `scripts/test-merge-verified-removed.sh`
exits 1 today and is invoked by nothing: its `check_file_present` targets the
pre-`skills/` layout, its `check_file_absent` targets no longer exist so they
pass vacuously, and it greps a store retired by `owb-07`. It is a red gate
nothing runs, which is why the red went unnoticed.
`scripts/.aet-work-orchestrator.log` is 1.8 MB, tracked, matched by no
`.gitignore` entry, read by nothing, and could not be added today —
`.pre-commit-config.yaml` sets `check-added-large-files --maxkb=500`.

## Intake Triage

- [x] Demonstrable: the tolerated reds and the failing script are both
      observable, and are recorded in
      `content/backlog/debt-gate-tolerates-known-intermittent-reds.md` and
      `content/backlog/debt-dead-tracked-artifacts.md`
- [x] Routed here because the deliverable is the readability of the gate signal,
      which is the PRD's rule applied to test output, not a fix to any one test

## Task List

1. Mark each of the three known intermittent failures `xfail(strict=False)` with
   the reason and the report that records it, so a green run means green and a
   pass still reports as `xpass` rather than being hidden — S (traces: R-7)
2. Add a short register of tolerated reds that the markers cite, so the set is
   enumerable and a marker cannot outlive its reason unnoticed — S (traces: R-7)
3. Delete the red script nothing invokes, and drop its entry from
   `tests/fixtures/uncovered-source-files.txt` — S (traces: R-7)
4. Delete the tracked orchestrator log and add it to the retired ignored paths so
   a consuming project still carrying it is reported — S (traces: R-7)
5. Assert in a test that the tolerated-red register matches the markers actually
   present, so removing a marker without removing its entry fails — S
   (traces: R-7)
6. Merge branch to main and verify integration — S

### Floor Check

- [x] The change is limited to one subsystem and maintains no architectural invariant
- [ ] Expected diff is below the calibrated floor threshold
- [ ] `Files to Modify` substantially overlaps a sibling it is ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

One box checked: this is test-suite and script hygiene, introducing no runtime
invariant. It is above the floor because of the register and its guard test.

## Rejected Alternatives

- **Diagnose the three flakes first** — rejected: two do not reproduce, and the
  marking is cheap, independent of ever finding the causes, and is what makes the
  gate readable in the meantime. Diagnosis stays open.
- **Move the flaky tests out of the default gate** — rejected: the loadgroup
  report offers it as an equal alternative, but removing a test from the gate
  loses the signal entirely, whereas `xfail(strict=False)` keeps it and reports
  an unexpected pass.
- **`skip` rather than `xfail`** — rejected: a skip does not run the test, so a
  flake that becomes a permanent failure is never observed.
- **Leave the log tracked and only ignore it** — rejected: it is 1.8 MB that
  nothing reads and that today's own pre-commit limit would refuse.

## Files to Modify

- `tests/orchestrator/test_integration_serialization.py`
- `tests/orchestrator/test_nightshift_rehearsal.py`
- `tests/test_aet_run_dispatch.py`
- `tests/fixtures/uncovered-source-files.txt`
- `tests/test_tolerated_reds.py` (new — covered by `test_tolerated_reds.py`)
- `src/aet/worktree.py`
- `scripts/test-merge-verified-removed.sh` (deleted)
- `scripts/.aet-work-orchestrator.log` (deleted)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] A full-suite run reports zero unexpected failures and names its expected
      ones
- [ ] No `scripts/*.sh` in the tree exits non-zero when invoked directly
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The markers disappear and the two artifacts return; the gate
is as readable as it was, which is the state that produced the 2026-08-28
misreading.

## Pipeline

`standard` — the change is small but alters how every future gate result is read.

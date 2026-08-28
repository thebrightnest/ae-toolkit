# Retro: a 22-attempt requeue loop cost $23.77 and every mechanism meant to stop it was inert

**Date:** 2026-08-28 · **Trigger:** an `aet run` of `pub-03` in the consuming
repository `dhl-agentic-tot` · **Layer:** `src/aet/failure.py`,
`src/aet/cli/orchestrator.py`, `src/aet/cli/mine_learnings.py`,
`src/aet/cli/ship.py`

## Provenance

The field evidence comes from the consuming repository: the sealed task record
`refs/aet/sealed/pub-03-comparison-publish-routing-plan` and the run log
`.agents/runs/run-20260827-164813-3nscrlh5/output.log`, both read directly, plus
the run's telemetry at
`~/.aet/telemetry/dhl-agentic-tot/main/2026-08-27/run-20260827-164813-3nscrlh5/`.
The findings were first written in that repository against an installed snapshot
(1.11.0, verified identical to source for every function cited here) and were
re-derived against the toolkit source on 2026-08-28.

Of the five mechanisms the original named, three had the wrong cause, one held,
and one — the loop's proximate cause — was missing. The original also recorded
the breaker's failure as unexplained and its evidence as self-contradictory; both
are settled here. The record carries one signature entry, not 21, and the reason
is reproduced below rather than hypothesised.

The project-level finding that accompanied the original — a missing rule about
escaping values rather than translating them, in the consuming repository's
`AGENTS.md` — was applied there and is not carried here.

## The Session

`pub-03` merged to that project's `main` as `23dfbf7`. Its own accounting:

| Measure | Value |
| --- | --- |
| State transitions | 77 — `ready → in_progress` ×22, `in_progress → failed` ×22, `failed → ready` ×21 |
| Recorded cost | $23.77 / 34,567,679 tokens |
| Failure signatures on the record | one, class `flaky`, stage `plan-approved` — 21 were recorded and overwritten |
| Distinct failure causes in the log | 40 × session-limit `429`, 1 × "connection lost while your computer was asleep" |

Roughly $23 of the $23.77 bought nothing: the `429` attempts return in 0.5–2.6s
with zero output tokens.

## Five Independent Stops, None of Which Fired

The loop is not one defect. Five mechanisms exist to stop exactly this, and each
was inert for its own reason. The first three are reproduced locally; the causes
below replace the ones this retro first recorded.

**Classification.** `classify()` returns `flaky` for the wording the harness
actually emits. `\bstatus` cannot match after the `_` in
`"api_error_status":429`, and the `session limit` pattern requires
`reached`/`exceeded` where the harness says `hit` and `resets`. All 44 result
envelopes in the run log classify as `flaky`; the telemetry records the same for
21 stage sessions at `exit_code: 1`. ADR-065 predicted this class of miss in its
Consequences and priced it at one requeue.
→ `docs/bugs/20260828-throttle-patterns-miss-the-harness-wording.md`

**The throttle stop.** ADR-065's remedy — stop the run, name the reset — cannot
fire for any input. Decision 2 keeps a `throttled` signature out of the task
record because a closed window is not breaker evidence; decision 3 detects the
class by reading that same record (`orchestrator.py:2922`). A correctly
classified throttle therefore records nothing, reads back as `environment`, and
requeues, with `stop_spawn: False`. Both decisions are implemented, and they
cancel.
→ `docs/bugs/20260828-throttle-remedy-cannot-see-its-own-class.md`

**The per-task breaker.** Threshold 3, absolute precedence over triage routing,
and `flaky` is countable — so attempt three should have quarantined regardless of
the misclassification. It could not: the child records the signature on the local
task ref and never pushes it, and the parent's first act on failure is
`_mark_failed`, which shells out to `aet state transition`, whose first act is a
`+refs/aet/*:refs/aet/*` fetch that force-resets that ref to origin's
pre-attempt copy. Reproduced locally — `signatures 1 → 0` — and the loss is not
specific to signatures: `cost` and delivered size travel the same unpushed path.
The defect needs `shared` posture, which needs an in-tree config, which no test
repo has.
→ `docs/bugs/20260828-fetch-discards-unpushed-record-writes.md`

**The stage record.** Every attempt after the first re-ran `aet-tdd →
aet-implement` over a completed implement commit, because a session group records
its stage once at the group boundary, after every evidence gate in the span
passes. Nothing reset the stage on requeue; it was never advanced. Same symptom
as D2/D3 of `aet-toolkit-defects.md`, third mechanism, second ~$24 measurement.
→ `docs/bugs/20260828-group-stage-advance-is-all-or-nothing.md`

**The miner.** `aet mine-learnings` reported `Repeated loops: 0` and
`Reports scanned: 0`, and `aet retro` emitted "No findings" in both buckets, for
the most expensive session in that project's history. The bucket has one source:
keyword-matching narrative markdown. The structured records the miner already
reads count the loop.
→ `docs/bugs/20260828-mine-learnings-cannot-see-a-requeue-loop.md`

## The Gate That Cannot Be Satisfied

Separately, `aet ship merge` refused the finished task for missing `aet-verify`
evidence. `verify` is a stage the pipeline walks — `synced → verified`,
`gate_default: critical-only` — so the original reading that no stage produces
the evidence was wrong about the cause and right about the outcome: three
components name three different artefacts for one evidence kind, and nothing
writes the path the gate checks. A critical-class task therefore reaches
`awaiting_merge` in a state the gate always rejects.
→ `docs/bugs/20260828-verify-evidence-has-three-contracts.md`

## What Generalises

**A defence-in-depth stop that cannot observe its own evidence is worse than no
stop,** because it is why nobody watches the first one. Four of the five
mechanisms above have passing tests that exercise the mechanism rather than the
outcome. `THROTTLE_TAILS` (`tests/failure/test_failure_taxonomy.py:153`) pins
wording no harness emitted. The breaker tests
(`tests/orchestrator/test_circuit_breaker.py:36-59`, `:184`) append signatures
directly, or call `_record_failure_on_task` directly, never driving a failing
stage through the finalize path that has to supply them. The session-group tests
(`tests/workflow/test_workflow.py:80-166`) validate group definitions; no test
fails a group midway and asserts what the task record then carries. The throttle
stop is asserted (`tests/failure/test_throttled_stops_the_run.py:112`) from a
hand-written record whose one legitimate writer refuses to produce it, so the
test and the code it guards describe behaviour that cannot occur. The end-to-end
rehearsal (`tests/orchestrator/test_nightshift_rehearsal.py`) runs a real batch
and asserts a breaker quarantine, but in shadow posture and at `threshold=1` —
the two conditions under which the ref overwrite is invisible. Each test proves
the code does what it says, and none proves the loop cannot happen.

**A test repo that no project resembles proves nothing about projects.** Shared
posture is what a configured project has and what every test fixture lacks, and
it is the switch that turns a working breaker into a silent one. Posture belongs
in the matrix of anything that writes a task record.

**A rule enforced at one call site is a comment, not an invariant.** The
push-after-write requirement was already understood: the merge-commit write
carried it, with a comment naming the fetch that would otherwise overwrite it.
Seven sibling writes did not, and nothing connected them. The fix is one helper
that states the reason once and is the only way to write a task record.

**A count of zero and an unscanned bucket must not render identically.** The
miner's `Repeated loops: 0` was read as evidence of absence by the retro command
downstream, which then reported no findings for a $24 loop.

## Action Items

| Item | Owner | Status |
| --- | --- | --- |
| Establish the harness exit code and the signature count from the field record | this retro | ✅ done — exit 1 throughout, one entry, 21 overwritten |
| Stop discarding unpushed task-record writes on fetch | `docs/bugs/20260828-fetch-discards-unpushed-record-writes.md` | ✅ fixed — `_save_task_record` replicates all eight direct writes; regression test runs in shared posture at the real threshold |
| Make the throttle class visible to the remedy that reads it | `docs/bugs/20260828-throttle-remedy-cannot-see-its-own-class.md` | ✅ fixed — a throttle records as `countable: False`; the breaker and systemic tally skip it |
| Widen `_THROTTLE_PATTERNS`, with the verbatim observed tails as regression cases | `docs/bugs/20260828-throttle-patterns-miss-the-harness-wording.md` | ✅ fixed — four patterns, verbatim tails, false-positive guards asserted |
| Amend ADR-065: the 185-attempt outcome it calls unreachable was reached, and decisions 2 and 3 cancel | `docs/adr/071-a-non-countable-failure-is-recorded.md` | ✅ recorded |
| Decide what credits a stage whose session failed | `docs/adr/069-stage-credit-is-earned-by-verdict.md` | ✅ recorded and implemented |
| Decide which artefact is verify evidence | `docs/adr/070-verify-evidence-is-the-verdict.md` | ✅ recorded and implemented |
| Record each stage inside a group as it completes | `docs/bugs/20260828-group-stage-advance-is-all-or-nothing.md` | ✅ filed |
| Derive `repeated_loops` from `stage` records | `docs/bugs/20260828-mine-learnings-cannot-see-a-requeue-loop.md` | ✅ fixed — counted per `(run, task, stage)` |
| Have the ship gate read the verdict the stage writes | `docs/bugs/20260828-verify-evidence-has-three-contracts.md` | ✅ filed |

## Filed, Not Yet Done

Everything this retro surfaced and did not fix has a home, so it is findable
without reading the session that produced it:

| Item | Filed as |
| --- | --- |
| Assert containment at the outcome, not per mechanism — the one test that would have caught all four inert stops at once | `docs/ideas/outcome-level-containment-testing.md` |
| Gate evidence does not travel with the task, which is why ADR-070 bounded its own fix | `docs/ideas/evidence-portability.md` |
| Concurrent task-ref writes lose a compare-and-swap under `--dist=loadgroup` — a tolerated red that hid a real one on 2026-08-28 | `docs/bugs/20260828-loadgroup-flake-on-concurrent-task-refs.md` |
| A forced `refs/aet/*` fetch discards local state with no diagnostic | `docs/TECHNICAL_DEBT.md` |
| The end-to-end rehearsal cannot observe posture-dependent defects | `docs/TECHNICAL_DEBT.md` |
| The orchestrator writes task records directly instead of through `aet state` | `docs/TECHNICAL_DEBT.md` |
| `aet-toolkit-defects.md` describes a 1.8.0 tree | `docs/TECHNICAL_DEBT.md` |
| Release the toolkit: none of these fixes reach a consuming project until its install moves past 1.11.0 | this table, until `aet-release-prep` runs |

## Outcome

All six items are closed in this repository, three of them under new ADRs. A run
that meets a provider limit now stops on the first attempt and names the reset; a
task that keeps failing for its own reasons quarantines at three; a group that
dies late keeps the stages it proved and tells the retry about the rest; and a
critical task can satisfy the ship gate with the verdict its stage writes.

One thing deliberately did not change: an interrupted stage with no evidence
binding still re-runs. ADR-069 explains why crediting it from commits was
rejected — in an unattended shift, a stage credited on partial work has its
remainder skipped silently.

The `--on-failure halt` workaround stays useful in the consuming repository until
its installed copy is upgraded past 1.11.0.

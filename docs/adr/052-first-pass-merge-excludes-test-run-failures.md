# Factory Metrics Read Stage Records, Not `test_run` Records

## Status

Accepted (2026-07-26). Refines ADR-035 (canonical factory-metric definitions), which requires
that a change to a metric definition be recorded as a new ADR rather than an edit. Sibling to
ADR-050 and ADR-051. Motivated by
`reports/2026-07-25-aet-performance-observability-review.md`; delivered by the
`telemetry-adapter-parity` PRD (`tap-01`), which lands before the detection work it protects.

## Context

ADR-035 defines **First-Pass Merge** as a settled task that reached `merged`, passed every verdict
kind its plan's gate routing required, has **no failed stage/`test_run` telemetry record**, and
carries no **Rework** — where rework is "repeated stage runs (stage telemetry records beyond the
first for any stage name) plus `failed → *` re-entry transitions."
`track_record.is_clean_merge` implements both clauses for `aet desk --eligibility`, `aet metrics`,
and the scoreboard.

Both clauses read a shared iterator, `track_record.iter_telemetry_task_records`, which yields
records of type `stage` **and** `test_run` (`track_record.py:74`). That is deliberate for the
failure clause, which ADR-035 states as "stage/test_run". It was never intended for rework:
`_repeated_stage_count` (`:103`) groups every yielded record by its `stage` field and counts
everything past the first — and `test_run` records carry a `stage` field
(`telemetry.test_run_record`). So a task that ran `make validate` three times during `implement`
scores +3 rework, and any stage with both a stage record and one test run scores +1.

Measured over the 127 tasks with stage/`test_run` telemetry in the three AET projects:

| Clause | Current (stage + `test_run`) | Stage records only |
| --- | --- | --- |
| Tasks with rework > 0 | **121 (95%)** | 25 (20%) |
| Tasks with a failed record | 52 | 27 |
| **Tasks passing both telemetry clauses** | **1 (1%)** | **93 (73%)** |

The first-pass-merge metric currently reports approximately **1%** — not because the factory is
failing, but because 418 phantom rework units were counted from test invocations. The
documentation and the code have said different things since ADR-035 landed; the rework clause is
a **defect against ADR-035's own wording**, which is the docs↔code reality gap that ADR's Context
paragraph names as the thing this program exists to kill.

The failure clause is a genuine definitional question rather than a defect, and it has its own
problem. `wirelog.is_test_command` anchors its patterns at the start of the command string, so it
misses `cd <worktree> && <test>` — the ordinary shape of an orchestrator agent's shell call — and
most runner wrappers; under Claude Code it sees nothing at all (ADR-050). Of the 313 test runs AET
does observe, 62 are failures, and the missed invocations are roughly twice that population and
disproportionately the ones a fixed detector would newly catch: the red step of a TDD loop, a fast
targeted re-run after an edit, an intermediate failure inside a `cd … && …` chain. Those are
expected behaviour in a working pipeline. Under the current definition, fixing detection would
push both clauses further down — more failures *and* more phantom rework — reporting a measurement
improvement as a quality collapse, and creating a standing incentive against improving
observability.

The other clauses do not have this problem. A failed **stage** record means an agent session
failed. A repeated **stage** record or a `failed → *` transition means the task genuinely went
around again. A failing **verdict** means a gate rejected the work. Each is a statement about the
task's path through the pipeline. A `test_run` is a statement about one shell command inside a
session — and after ADR-051, roughly a quarter of `test_run` rows are not even measurements.

## Decision

**`test_run` records are removed from the factory metrics entirely. Both the failure clause and
the rework clause read `stage` records only.**

First-Pass Merge keeps every other clause unchanged:

1. The task reached `merged`.
2. Every verdict kind required by its plan's **Stage Routing Key** passes.
3. It has no failed **stage** telemetry record.
4. It carries no **Rework**, where rework counts repeated **stage** records beyond the first per
   stage name, plus `failed → *` re-entry transitions.

Concretely:

- **The rework correction is a defect fix.** ADR-035 item 2 already says "stage telemetry
  records"; the counting core is brought into line with the definition that was always written
  down. It is recorded here rather than fixed silently because it moves a published number by
  two orders of magnitude.
- **The failure-clause change is a definitional change.** ADR-035 item 1 says "stage/`test_run`";
  this ADR narrows it to stage records. Both provenances are removed: a claimed record cannot fail
  (ADR-051 — the verdict emitter only fires on a pass), and an observed failure is an
  intra-session event, not a pipeline outcome.
- **Sharing an iterator is not sharing a definition.** `iter_telemetry_task_records` may keep
  yielding both types for other callers, but each metric predicate states which record types it
  reads. The two clauses are no longer allowed to inherit a record set by accident.

**Ordering is part of the decision.** This lands *before* the detection and adapter work, so the
metrics absorb a definition change on a stable corpus rather than moving underneath a measurement
change. The re-baseline is computed and recorded at that point: the before/after first-pass-merge
rate over the existing archive, with the delta attributed to the two clauses separately.

The metrics stay **analytics-only** (ADR-031, ADR-035 item 4) and **retroactively derived**
(ADR-035 item 5). No code path gates on them, and no `first_pass` flag is stamped.

## Consequences

- The reported first-pass-merge rate rises sharply — the telemetry clauses alone go from 1% to
  73% of tasks over the current archive. Most of that is the rework defect fix. It is a
  correction, is measured, and must be published as such; it is not an improvement in delivery.
- **Rework counts drop for most tasks** and become a usable signal for the first time. Any prior
  analysis citing rework counts is invalid and should be re-derived, not adjusted.
- The metrics become invariant to detector fidelity. Future observability work — a third adapter
  reader, a wider runner registry — can no longer move them, which is the property that makes them
  worth tracking at all.
- The track record is re-baselined, as ADR-035 warned any definition change would be. Comparisons
  spanning 2026-07-26 must state which definition they use.
- Intra-session test failures and repeated test runs lose their representation in the factory
  metrics. They remain fully visible as `test_run` telemetry and in the panel. If "red-run
  density" or "validation churn" is wanted as a signal later, each belongs in its own measure,
  computed over observed records only (ADR-051), and not folded back into a merge-quality metric.
- A genuinely broken merge — code merged with a failing suite — is still caught, by the QA verdict
  and by the stage-failure clause. Nothing here weakens a gate; it removes a proxy the gates
  already cover directly.

## Alternatives Considered

- **Fix only the rework defect and keep the failure clause.** Rejected: it leaves the metric
  sensitive to detector fidelity, so the detection work would still publish a false regression.
  Both clauses have the same root cause and are corrected together.
- **Keep both clauses and accept the numbers.** Rejected: a metric that reports 1% is not
  measuring the factory, and preserving it would report better observability as worse quality —
  the precise dynamic ADR-031 exists to prevent.
- **Count only the *last* `test_run` per stage, so a red-then-green loop passes.** Rejected: it
  encodes an assumption about loop shape the record set does not support (ordering across emitters
  is not reliable), and it still breaks the moment detection improves and a new "last" run
  appears.
- **Count only `source == "verdict"` failures.** Rejected as vacuous: the verdict emitter fires
  only on a passing verdict, so the clause could never fire. Unreachable logic in a canonical
  definition is worse than no logic.
- **Fix detection first, then adjust the definitions once the damage is visible.** Rejected: it
  publishes a false regression to the desk and the scoreboard in the interim, and it invites the
  detector fix to be blamed for a number that was already wrong before it.
- **Weight repeated test runs into a separate "validation churn" metric now.** Rejected as scope:
  it is a plausible future measure, but inventing it in the same change that corrects a broken one
  would make the re-baseline impossible to read.

# Technical Debt

Known, accepted shortfalls that survived a merge. Each entry records what was
deliberately left undone, why it was acceptable at the time, and what would
trigger fixing it.

New entries go at the top of their section. When an item is fixed, delete it —
the git history is the archive.

## Tooling and project setup

### No coverage tool is configured

*Recorded: 2026-07-27 — Source: tap-02-shared-runner-registry, aet-qa stage*

`pyproject.toml` declares no `coverage` or `pytest-cov` dependency, and the
`.coverage` file at the repo root is stale. The aet-qa stage requires a
coverage check on new modules, so it fell back to the standard-library `trace`
module to prove `src/aet/test_runners.py` was exercised (77/77 lines, 0 missed).

That fallback works but is per-run, per-file, and manual — it produces no
project-wide number and no regression signal.

**Why accepted:** the QA skill's own instruction is to flag a missing coverage
tool as a setup gap rather than silently skip the check, which is what happened.
The gap predates tap-02 and is out of that plan's scope.

**Trigger to fix:** any plan that wants a coverage threshold as a gate, or the
next time a QA stage has to hand-roll `trace` to answer the coverage question.

## Telemetry adapter parity (tap-01…tap-06)

### Wrapper normalisation narrowed for `npm run`, `yarn`, `pnpm`

*Recorded: 2026-07-27 — Source: tap-02-shared-runner-registry (R-1), branch tap-02 scope only*

The locked design in `docs/prds/telemetry-adapter-parity-prd.md` unwrapped these
as generic wrappers, so `yarn vitest` would normalise to `vitest`. As built,
only their `test` forms are runner-table entries (`npm run test` → `npm test`,
`yarn test`, `pnpm test`); arbitrary runners are not unwrapped, so `yarn vitest`
and `npm run vitest` do not match and their runs go unrecorded.

**Why accepted:** this is the conservative direction under the plan's own
false-positive-avoidance rule — a missed run costs telemetry volume, a wrong
match records a fabricated one.

**Trigger to fix:** telemetry showing those command shapes actually occur in the
tracked projects. Widening is a small registry change in `src/aet/test_runners.py`.

### Superset-replay fixture is synthetic, not captured

*Recorded: 2026-07-27 — Source: tap-02-shared-runner-registry, aet-review flag*

The superset-replay test builds its input by hand instead of replaying a real
captured wire log. It therefore proves the registry's behaviour against the
shapes the author thought of, not against the shapes the field actually emits.

**Why accepted:** non-blocking review flag; the synthetic fixture still covers
every runner-table entry and the review passed on it.

**Trigger to fix:** the first detection miss found in production telemetry that
the synthetic fixture did not predict — replace it with a captured log then.

### Stale code anchors in the parity PRD

*Recorded: 2026-07-27 — Source: tap-02-shared-runner-registry, aet-review flag*

`docs/prds/telemetry-adapter-parity-prd.md` cites file/line anchors that the
tap-02 implementation has already moved. `aet-sync-docs` reads those anchors, so
they will drift further with each of tap-03…tap-06.

**Why accepted:** the PRD spans tap-01…tap-06 and only tap-02 is built;
rewriting anchors mid-sprint would churn them again on every subsequent plan.

**Trigger to fix:** when tap-06 lands and the PRD is synced as a whole.

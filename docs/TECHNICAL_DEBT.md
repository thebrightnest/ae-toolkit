# Technical Debt

Known, accepted shortfalls that survived a merge. Each entry records what was
deliberately left undone, why it was acceptable at the time, and what would
trigger fixing it.

New entries go at the top of their section. When an item is fixed, delete it —
the git history is the archive.

## Tooling and project setup

### A forced `refs/aet/*` fetch discards local state with no diagnostic

*Recorded: 2026-08-28 — Source: docs/bugs/20260828-fetch-discards-unpushed-record-writes.md*

`GitRefsBackend.fetch` fetches `+refs/aet/*:refs/aet/*`, so every `aet state`
invocation force-resets each local task ref to origin's copy. That is now safe
for the orchestrator's own writes, which replicate through
`_save_task_record`, but the fetch itself still says nothing when it overwrites a
local ref whose content differs from the remote's.

**Why accepted:** the refs hold JSON blobs, not commits, so there is no ancestry
to compare and no merge rule to apply — "the remote wins" is the only available
semantics. Push-after-write is the guard, and it is in place. A diagnostic would
have to diff blob content on every fetched ref, on a hot path that runs before
every transition.

**Trigger to fix:** a second writer appears that cannot push (a read-only clone,
a CI checkout), or any report of a task record losing a field again.

### The end-to-end rehearsal cannot observe posture-dependent defects

*Recorded: 2026-08-28 — Source: docs/retros/2026-08-28-aet-run-retro.md*

`tests/orchestrator/test_nightshift_rehearsal.py` runs a real unattended batch
and asserts a breaker quarantine, which looks like coverage for the runaway-loop
class. It cannot see that class: its temp repo has no in-tree
`.agents/aet-config.json`, so the posture is `shadow`, pushes are suppressed, and
origin never carries `refs/aet/*`; and it patches `should_quarantine_task` to
`threshold=1`, so it never tests accumulation across attempts.

**Why accepted:** the two focused tests added on 2026-08-28
(`test_task_record_replication.py`, `test_stage_credit_on_failure.py`) cover the
mechanisms in shared posture at real thresholds. Reshaping the rehearsal is a
fixture change whose other assertions depend on the current single-run shape, and
a second real batch run costs wall-clock in every `make validate`.

**Trigger to fix:** the containment work in
`docs/ideas/outcome-level-containment-testing.md`, which needs this fixture
anyway.

### The orchestrator writes task records directly instead of through `aet state`

*Recorded: 2026-08-28 — Source: docs/bugs/20260828-fetch-discards-unpushed-record-writes.md*

ADR-055 and `_record_stage`'s docstring both describe `aet state` as the sole
writer of a task record. The orchestrator is a second writer at eight sites
(failure signatures, gap analysis, integration failure, merge commit, delivered
size, three cost roll-ups). They are correct now — each replicates — but the
single-writer rule the fetch refspec assumes is still not true.

**Why accepted:** routing them through `aet state` needs CLI surface for each
field, which is a larger change than the defect required, and the helper makes
the current arrangement honest.

**Trigger to fix:** a third writer, or a field whose write needs validation the
CLI already performs.

### `aet-toolkit-defects.md` describes a 1.8.0 tree

*Recorded: 2026-08-28*

The root-level `aet-toolkit-defects.md` is the document an operator loads before
`aet run`. It was written on 2026-08-12 against ae-toolkit 1.8.0 in a consuming
project, and its line numbers, several statuses, and its operating checklist have
drifted. D3 (`_record_stage` no-ops under `git-refs`) is fixed in the current
source — `_record_stage` resolves the task ref and routes through
`aet state set-stage` — and the checklist predates the 2026-08-28 fixes.

**Why accepted:** re-verifying thirteen items against the current tree is its own
task, and each one wrongly marked open is a false alarm rather than a hazard.

**Trigger to fix:** the next operator session that follows the checklist, or the
next release that changes any path it names.

### Skills still name `.agents/work-queue.json` as the board

*Recorded: 2026-08-27 — Source: aet-evolve retro, planning-pipeline contradictions*

The `git-refs` backend stores the board in `refs/aet/tasks/*` with a
`refs/aet/meta/queue` envelope. `.agents/work-queue.json` is a path the backend no
longer writes, and `aet setup verify` already warns that `.gitignore` names it.
Seventeen references survive across fifteen files in six skills — `aet-work`
(7), `aet-pipeline-plan` (4), `aet-plan` (2), `aet-setup` (2),
`aet-validate-scope` (1), `aet-evolve` (1), plus reference files, examples, and
`aet-setup/checklist.md`.

One of the seventeen was corrected in passing when `aet-plan`'s completion item 5
was rewritten. The rest are untouched.

**Why accepted:** the occurrences are not uniformly wrong.
`aet-work/references/migration-aet-state.md` and `upgrading-existing-project.md`
describe migrating *from* that layout, where naming the old path is the point. A
blind replace would corrupt them, and the 2026-08-23 learning is specifically
about sweeps reported complete while wrong copies survive in reference files and
templates. The audit needs per-file judgment, which is more than the retro that
found it should carry.

**Trigger to fix:** the next skill edit in `aet-work` or `aet-setup`, or any
session where an agent reads or writes `.agents/work-queue.json` because a skill
told it to.

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

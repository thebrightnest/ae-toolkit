# Bug Report: the `aet ship` family cannot resolve a plan for any task whose plan file is not committed

## Metadata

- **Reported:** 2026-08-19
- **Severity:** high
- **Status:** open

## Symptoms

`aet ship merge <task-id>` refuses to run for a task that is otherwise ready to
ship:

```
$ aet ship merge gdl-01-plan-floor-guardrail --dry-run
⛔ Plan not found: 'gdl-01-plan-floor-guardrail' is not a .md path and
   docs/plans/gdl-01-plan-floor-guardrail.md does not exist. Pass the full plan path.
```

There is no path to pass. The plan file does not exist on `main`, on the task
branch, or anywhere in the working tree — by design.

## Reproduction Steps

1. Take any task whose plan was never committed to `docs/plans/` (the normal case
   under R-19 — see Root Cause).
2. Run `aet ship merge <task-id>` (or `gate`, `open`, `split`).
3. Observed: `⛔ Plan not found`, exit before any gate work. The advice "Pass the
   full plan path" cannot be followed, since no such file exists.

Observed on `gdl-01-plan-floor-guardrail` and `owb-08-single-source-ledger-path`,
both listed by `aet desk` as `awaiting_merge` with complete green evidence.

## Root Cause

Two parts of the system disagree about where a plan lives.

**The orchestrator treats plans as ephemeral.** `render_task_plan`
(`src/aet/worktree.py:316-323`) writes the plan into the worktree from the portable
spec carried on the task record (R-19), falling back to `plan_file` only for legacy
records. `run_task` prints "Plan durability is deferred to the PR (docs/plans/ only)".
The plan is a render target, not a tracked artifact.

**The ship family treats plans as committed files.** All five `ship` entry points
resolve their argument through `plan_parser.resolve_plan_arg`
(`src/aet/cli/ship.py:329, 541, 799, 886, 1113` → `cmd_ship`, `cmd_gate`, `cmd_open`,
`cmd_split`, `cmd_merge`). That resolver is filesystem-only
(`src/aet/plan_parser.py:613-629`): a bare id becomes `docs/plans/<id>.md`, and if
that file is not on disk it raises. It never consults the task record that the
orchestrator just rendered from.

So the closer a project follows the ephemeral-plan design, the more reliably the
ship commands fail. Tasks reach `awaiting_merge` through the orchestrator and then
cannot be shipped by the tool meant to ship them.

Existing tests did not catch it because they construct plan files on disk before
invoking ship, which is precisely the condition the runtime no longer guarantees.

## Suggested Fix

Give `resolve_plan_arg` — or a ship-local wrapper — the same fallback the
orchestrator has: when `docs/plans/<id>.md` is absent, look up the task record and
render the portable spec to a temporary plan path for the gate to read. Failing that
lookup (no record, no spec) is the only case that should raise, and the message
should name the task id rather than advise passing a path that cannot exist.

## Regression Test

None yet — this report is filed open, no fix applied.

A regression test should assert that `aet ship gate <task-id>` resolves for a task
whose record carries a spec and whose `docs/plans/<id>.md` does not exist.

## Validation

- [ ] Reproduction steps no longer trigger the bug
- [ ] Existing test suite passes with no new failures
- [ ] No regressions observed in related functionality

## Lessons Learned

- **Pattern:** same shape as the `create_worktree` fall-through fixed the same day
  (`20260819-create-worktree-fallthrough-crash.md`) — one part of the system
  deliberately stopped guaranteeing something, and a consumer kept assuming it.
- **Prevention:** when a design decision removes an artifact (R-19 making plans
  ephemeral), audit every consumer that reads it, not just the producer that
  stopped writing it.
- **Reference:** R-19; `src/aet/worktree.py:316`; `src/aet/plan_parser.py:613`.

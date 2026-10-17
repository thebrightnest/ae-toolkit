---
subject: skill-set-retirement
relates: [17, 38, 39, 66]
---

# Retire aet-work, aet-extract-stack, and aet-upgrade

## Status

Accepted (2026-10-17). Delivered by `RVS-01` (aet-work) and `RVS-02`
(aet-extract-stack, aet-upgrade) (PRD:
`docs/prds/retire-vestigial-skills-prd.md`).

## Context

Three of the distributed skills no longer earn their place.

- **`aet-work`** was the home of the queue code until ADR-038 moved it to
  `src/aet/`. What remained is a manual of `aet` subcommands with almost no
  judgment, which ADR-039 says belongs in the CLI. It also competes with
  `aet-drive` for the same triggers ("night shift", "AFK mode", "run all
  tasks"), still describes "sequential" execution although `aet run` is
  pipelined, describes a JSON-backend hash removed in 1.10, and calls plans
  the source of truth against ADR-061.
- **`aet-extract-stack`** copies a working project's CI and tooling into a
  scaffold. It is a one-off job, not a pipeline step. Nothing routes to it.
- **`aet-upgrade`** writes upgrade plans without the frontmatter intake
  requires, so its output has no path to `aet sprint add`. Nothing routes to
  it either. Its risk table, breaking-change template, and the rule that
  upgrades are critical-class work are worth keeping.

## Decision

1. **Retire all three skills.** `skills/aet-work/`, `skills/aet-extract-stack/`,
   and `skills/aet-upgrade/` are removed. Git history keeps them recoverable.
2. **Queue curation and residual-failure handling live in `aet-drive`.** It
   takes over the queue triggers, offers the Plan Backlog when the Board has no
   ready tasks, and admits only the plans the user names through
   `aet sprint add` (ADR-066). After a run it reports the Failure Class the
   engine's Triage (ADR-030) recorded and moves a task forward only on the
   user's word. It never assigns a class of its own.
3. **References are split by reader.** Operator references move to
   `docs/reference/queue/`. The plan-author part of the frontmatter contract
   goes into `skills/aet-plan/references/work-queue-format.md`; parser
   internals go to `docs/reference/queue/frontmatter-parsing.md`. The
   one-time `migration-aet-state.md` is deleted.
4. **Upgrades fold into `aet-plan`.** The breaking-change procedure, risk
   table, and template move to `aet-plan`'s references. An upgrade plan is an
   ordinary plan file that declares `work_class: critical`.
5. **Link pruning is narrow.** `aet setup skills` removes only links that
   point into a toolkit `skills/` root and whose target is gone.
6. **History is not rewritten.** CHANGELOG, release notes, other PRDs,
   archived plans, ADR-020, and ADR-039's inventory stay as written. Internal
   "aet-work" identifiers (module docstrings, `.agents/aet-work.json`, log
   names, test names) are not renamed.

## Consequences

- Queue execution is the CLI plus one skill, `aet-drive`.
- Hand-offs that said "run aet-work" now say `aet sprint add` then
  `/aet-drive`, or `aet run-one <id>`.
- Doc rules that pinned invariants on `aet-work` files are retargeted to the
  new locations; the invariants are unchanged.
- Users who type `/aet-work` get nothing; `aet-drive` answers the same
  intents. Copy-based installs keep stale directories until deleted by hand.

## Alternatives Considered

- **Put curation in `aet-prime`** — rejected: it would split the queue journey
  across two skills; `aet-prime` routes intent and does not manage the board.
- **Move every reference into `docs/`** — rejected: plan-author facts are read
  by the `aet-plan` agent, so they stay with that skill.
- **Delete `aet-upgrade` outright** — rejected: the risk table and template
  are still useful and cost little to keep inside `aet-plan`.
- **Rename internal "aet-work" identifiers** — rejected: churn across code,
  config paths, and tests with no user-facing gain.

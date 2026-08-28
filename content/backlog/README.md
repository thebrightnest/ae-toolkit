# Backlog

Every known-but-unstarted item in one place: one file per item, with the
metadata that decides when it gets picked up. Items are not a queue — nothing
here is scheduled. They are the things that would otherwise live only in a
session transcript.

An item leaves this folder by being planned (a PRD in `docs/prds/`, plans in
`docs/plans/`) or by being deleted when it is done or no longer true. Git history
is the archive; there is no "done" section.

## Types

| Type | What it is | What closes it |
| --- | --- | --- |
| `debt` | An accepted shortfall that survived a merge. Records why it was acceptable and what would trigger fixing it. | The fix lands, or the trigger fires and it becomes a plan. |
| `idea` | A change nobody has decided to make. Some need a decision (an ADR) before they can be planned at all. | An ADR settles it, a PRD plans it, or it is dropped. |
| `roadmap` | A multi-phase initiative with tracks, kept out of `docs/plans/` because it is not atomic (ADR-006). | Its tracks are planned and land. |

## Frontmatter

Each file carries `type`, `status`, `recorded`, `source`, `trigger`,
`depends_on`, and `blocks`. `trigger` is the field that matters most: an item
with no trigger is waiting on a decision, and an item whose trigger has fired is
work that is being ignored.

## Ready to plan

Nothing blocks these but the decision to do them.

| Item | Type | Why now |
| --- | --- | --- |
| [Assert runaway containment at the outcome](outcome-level-containment-testing.md) | idea | Four independent stops were inert at once on 2026-08-27 and every one had a passing test. Depends on the rehearsal-fixture debt item, which it also fixes. |
| [AET package extraction](aet-package-extraction-roadmap.md) | roadmap | Track A is in planning; `docs/prds/namespace-consolidation-prd.md` R-8 depends on this staying accurate. |

## Needs a decision first

These cannot be planned until something is settled, usually in an ADR.

| Item | Type | Decision needed |
| --- | --- | --- |
| [Gate evidence does not travel with the task](evidence-portability.md) | idea | Where verdicts live so they survive leaving the machine that wrote them — and first, whether a verdict is a fact about a tree or about a run. |
| [Do per-branch verdicts compose across a parallel batch?](parallel-batch-verdict-composition.md) | idea | What per-branch QA, review and security passes say about the union of the branches. Contests an assumption inside ADR-045. |

## Waiting on a trigger

| Item | Type | Trigger |
| --- | --- | --- |
| [A forced `refs/aet/*` fetch has no diagnostic](debt-forced-fetch-has-no-diagnostic.md) | debt | A writer that cannot push, or another task record losing a field. |
| [The rehearsal cannot observe posture-dependent defects](debt-rehearsal-cannot-observe-posture.md) | debt | The containment work above, which needs this fixture. |
| [The orchestrator is a second writer of task records](debt-orchestrator-is-a-second-writer.md) | debt | A third writer, or a field whose write needs CLI validation. |
| [`aet-toolkit-defects.md` describes a 1.8.0 tree](debt-toolkit-defects-doc-is-stale.md) | debt | The next operator session that follows its checklist. |
| [Skills still name `.agents/work-queue.json`](debt-skills-name-the-old-queue-path.md) | debt | The next skill edit in `aet-work` or `aet-setup`. |
| [No coverage tool is configured](debt-no-coverage-tool.md) | debt | A plan that wants a coverage gate, or another QA stage hand-rolling `trace`. |
| [Wrapper normalisation narrowed](debt-wrapper-normalisation-narrowed.md) | debt | Telemetry showing `yarn <runner>` shapes occur in tracked projects. |
| [Superset-replay fixture is synthetic](debt-superset-replay-fixture-is-synthetic.md) | debt | The first detection miss the synthetic fixture did not predict. |
| [Stale code anchors in the parity PRD](debt-parity-prd-code-anchors-are-stale.md) | debt | tap-06 landing, when the PRD is synced as a whole. |
| [An impact-scoped gate reports green over a standing red](debt-impact-scope-can-hide-a-standing-red.md) | debt | The second pre-existing failure found by a scope widening rather than by the change that caused it. |
| [Enrich CLI help at the source](enrich-cli-help-at-the-source.md) | idea | The next divergence between skill prose and `--help`. |
| [Plain-text rendering for all non-TTY output](plain-text-all-non-tty-output.md) | idea | Measured token cost, or the next CLI rendering change. |

## Blocked on measurement

Both are efficiency levers that cannot be sized with the telemetry that exists.

| Item | Type | Blocked on |
| --- | --- | --- |
| [Shorten the long implement/QA session](cfg-01-session-efficiency.md) | idea | Turn-level telemetry. |
| [Deterministic QA-freshness suppression](deterministic-qa-freshness-suppression.md) | idea | A run that demonstrates the redundant re-run cost. Sibling of the item above, same gap. |

## Dependencies

Only two edges exist today, and both matter:

- `outcome-level-containment-testing` → `debt-rehearsal-cannot-observe-posture`:
  the containment test needs the fixture the debt item describes, and building it
  retires the debt.
- `deterministic-qa-freshness-suppression` → `cfg-01-session-efficiency`: the same
  telemetry gap blocks both, and the second is the smaller half of the first.

`evidence-portability` blocks any future attempt to widen a gate to check
evidence written on another machine — ADR-070 already bounded one such attempt.

## Where these came from

`docs/TECHNICAL_DEBT.md` (one section per item), `docs/ideas/` (one file per
item), and `docs/roadmaps/`. The idea and roadmap files kept their slugs, so a
reference to an old path resolves by directory alone.

`docs/roadmaps/` remains the destination ADR-006 and the planning skills name for
non-atomic planning output; this folder holds the backlog, not that contract.

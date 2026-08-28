---
type: idea
status: parked
recorded: 2026-08-21
source: docs/prds/cli-discovery-cost-prd.md
trigger: >-
  The next divergence found between skill prose and `--help` semantics.
depends_on: []
blocks: []
---

# Idea: Enrich CLI Help at the Source

- **Status:** Parked (2026-08-21). Deferred from `docs/prds/cli-discovery-cost-prd.md` Non-Goals.
- **Origin:** Audit finding during CLI discovery cost planning.

## Summary

The discovery-cost PRD makes the correct leaf command reachable in **one hop** (R-1). It does
not make that one hop **sufficient**. An audit of `skills/` found zero hand-copied option
tables — but ~25 files carrying semantics that `--help` does not have:

| Skill prose | What `--help` says |
|---|---|
| `--on-failure={triage\|continue\|halt}` — "`triage` spawns a cheap triage session that decides whether to requeue a transient failure or quarantine a design defect" | `--on-failure  triage\|continue\|halt` |
| `--follow` — "does **not** tail or stream the run log; it waits silently" | `--follow  Follow an existing run id.` |
| `--force` — "prints a loud warning and can corrupt a live run, so prefer re-running after the batch" | `--force  Override a live run lease…` |

The skills are not duplicating help. They are **compensating for it being thin**. That is why an
agent loads a 313-line skill to answer what looks like a syntax question: it walks to `--help`,
finds the flag named but not explained, and goes looking for meaning elsewhere.

## The idea

Move fail semantics, enum-value meanings, and danger warnings out of skill prose and into Typer
`help=` strings and command epilogs, so the generated surface carries them and skills keep only
workflow judgment (when to run, what it means for the sprint).

## Why it was deferred

- It touches every command, not a single rendering path.
- It requires deciding, per string, whether a sentence is CLI semantics or workflow judgment —
  a line the discovery-cost PRD deliberately did not have to draw, because R-4 is preventive
  rather than remedial.
- Done carelessly it would bloat `--help` and undo R-1's byte win. It needs a length budget.

## What it would take to pick it up

1. Classify every `--flag` mention across `skills/` as CLI semantics vs workflow judgment.
2. Set a per-command byte budget for help text so R-1's one-hop index stays cheap.
3. Migrate CLI semantics into `help=` / epilogs; leave judgment in skills.
4. Confirm `docs/CLI.md` regenerates with the enriched text and skills lose nothing.

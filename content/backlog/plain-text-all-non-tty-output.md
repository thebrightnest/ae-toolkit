---
type: idea
status: parked
recorded: 2026-08-21
source: docs/prds/cli-discovery-cost-prd.md
trigger: >-
  Measured token cost of box-drawing output, or the next change to CLI rendering.
depends_on: []
blocks: []
---

# Idea: Plain-Text Rendering for All Non-TTY Output

- **Status:** Parked (2026-08-21). Deferred from `docs/prds/cli-discovery-cost-prd.md` Non-Goals.
- **Origin:** Scope decision during CLI discovery cost planning. The PRD ships plain-text
  rendering for **help and error output only** (R-2); this extends it to the rest of the CLI.

## Summary

Rich box-drawing characters (`│ ─ ╭ ╮ ╰ ╯`) carry zero information to a non-interactive
consumer but are paid for in tokens on every command an agent runs. `aet --help` alone is
4,307 bytes, a substantial fraction of which is border. The same applies to `status`, `desk`,
`gate review`, `report`, and `metrics` — commands agents run far more often than help.

## Why it was deferred

Blast radius. Help and error output have no machine consumers inside the repo, so R-2 is safe
to ship narrowly. The other commands may have tests asserting on current formatting, and
`status` / `report` output is read by skills and possibly parsed. Extending the change requires
an audit of those consumers first, which is a different and larger piece of work than the
discovery-cost PRD scoped.

## What it would take to pick it up

1. Inventory every command that renders through Rich, and every test asserting on its output.
2. Identify which outputs have machine consumers (skills, orchestrator, panel) versus
   human-only consumers.
3. Measure the per-command byte saving to confirm the win justifies the test churn.
4. Apply the same non-TTY detection R-2 establishes, command by command.

## Prerequisite

R-2 of the CLI discovery cost PRD, which establishes the non-TTY detection mechanism this
would reuse.

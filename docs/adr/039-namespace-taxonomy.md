# Namespace Taxonomy: Deterministic Code vs. Judgment Skills

## Status

Proposed

## Context

The 2026-07-19 tooling-usage retro exposed namespace collisions between CLI subcommands and standalone binaries/skills (`aet ship` vs. bare `ship`, `aet evolve` vs. `aet-evolve` skill). The toolkit needs a durable taxonomy that decides what becomes code/CLI and what stays a skill, plus naming conventions that prevent future collisions.

## Decision

_TBD — this ADR is the deliverable of `nc-01-namespace-taxonomy-adr`. Populate with the settled deterministic/judgment split, per-side naming conventions, collision table, and rename spec once `nc-01` is implemented._

## Consequences

- Provides the naming source of truth for `pkg-11` (Typer consolidation).
- Resolves the `ship`/`review`/`plan`/`sync`/`evolve` collisions atomically and alias-free.

## Rejected Alternatives

_TBD._

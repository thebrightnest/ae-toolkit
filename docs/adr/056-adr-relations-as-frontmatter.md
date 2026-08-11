---
subject: documentation-invariants
---

# ADR Relations Are Declared in ADR Frontmatter

## Status

Accepted (2026-08-11). Extends ADR-040 (Documentation Invariants Are Data).
Implements requirement R-9 of the structural-review-tier-2 PRD.

## Context

ADR-040 made documentation governance rules data-driven through
`.agents/doc-rules.yaml`. The rule grammar is a public contract, so adding a new
rule type requires a new ADR. The structural review found that the docs corpus
itself suffers from the same drift class the rule engine was built to catch:
multiple live documents describing the same subject with contradictory details,
while a newer document that supersedes an older one is not machine-readable.

Three live contradictions were known at acceptance time:

1. **Intake-commit rules** — four surfaces agreed textually that no commit or
   push happens at intake, but nothing pinned the agreement as data.
2. **Direct-JSON-edit permission** — one doc permitted direct JSON mutation
   while another mandated `aet state transition` for the same repair.
3. **Footer-format strings** — a template referenced a deleted skill name while
   the canonical skill emitted the current name.

The review required a self-checking corpus: one subject must resolve to exactly
one live ADR, and the rule engine must enforce it.

## Decision

1. **ADR frontmatter gains two optional keys.** Every ADR may declare:
   - `subject:` — a string or list of strings naming the architectural subject(s)
     the record covers.
   - `supersedes:` — a list of ADR numbers (e.g. `[10, 34]`) or identifiers
     (e.g. `["ADR-010", "ADR-034"]`) that this ADR replaces.

2. **Supersession is global.** If ADR *N* names ADR *M* in `supersedes:`, ADR *M*
   is treated as not live for any subject, regardless of which subjects *M*
   declares. This matches the immutable-ADR model: a superseded record is
   historical, not partially current.

3. **`aet docs lint` gains the `unique_live_subject` rule type.** A rule targets
   a directory of ADR markdown files and fails when any subject is declared by
   more than one live ADR. The violation message names the subject and all live
   ADR identifiers.

4. **Two files are excluded from evaluation.** `000-template.md` (the authoring
   template) and `README.md` (the index) are never evaluated as live rules,
   because their purpose is instruction and navigation, not architectural truth.

5. **Malformed frontmatter fails closed.** An ADR with an unparseable or
   structurally invalid frontmatter block produces a diagnostic violation,
   because the lint cannot determine whether the file would introduce a
   contradiction.

## Consequences

- The corpus becomes self-checking: a new ADR that claims an already-live
  subject breaks `aet docs lint` until the contradiction is resolved.
- Supersession edges are explicit and versioned, so a reader can trace why an
  older ADR is no longer current.
- The rule grammar extension is itself governed by an ADR, preserving ADR-040's
  contract.
- Skill and convention docs that repeat ADR-derived rules can now be guarded by
  `must_contain` / `must_not_contain` rules, while the ADR lineage that
  authorizes those rules is guarded by `unique_live_subject`.

## Alternatives Considered

1. **Derive supersession from the `## Status` prose section** — Rejected. Prose
   status is not machine-checkable; the lint must derive liveness from data
   (ADR-040's own principle).
2. **Hand-maintained current-rules digest instead of frontmatter** — Rejected. A
   hand-maintained copy is the drift pattern R-9 exists to kill.
3. **Substring-only rules for the known contradictions, no subject lint** —
   Rejected. It pins today's three instances but leaves the defect class
   uncatchable.

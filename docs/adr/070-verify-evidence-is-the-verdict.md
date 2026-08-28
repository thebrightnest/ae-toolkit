---
subject: verify-evidence-artifact
relates: [31, 67]
---

# Verify Evidence Is the Verdict the Stage Writes

## Status

Accepted (2026-08-28). Motivated by
`docs/bugs/20260828-verify-evidence-has-three-contracts.md`.

## Context

Three components named three different artefacts for one evidence kind:

| Component | Artefact |
| --- | --- |
| Workflow and evidence machinery | verdict JSON at `<reports>/<slug>/<task-id>/verify.json` |
| `aet ship gate` | markdown at `.agents/verify/<task-id>-evidence.md` |
| `aet-verify` skill | `/tmp/aet-reports/<task-id>/evidence/`, and no verdict at all |

Nothing wrote the path the gate checked. A `work_class: critical` task therefore
reached `awaiting_merge` in a state the gate always rejected, and `awaiting_merge`
has no legal transition back, so the only route through was a hand-written file
at a path no producer knew about. The gate was not checking whether verification
happened; it was checking whether an operator knew a convention.

The workflow already resolves the requirement correctly — `synced → verified`
carries `evidence: "verify"` and `gate_default: "critical-only"`, and
`gate.required_evidence` reads it (POH-03, ADR-067). Only the artefact disagreed.

## Decision

**The verdict is the evidence, and the workflow is the only place an evidence
kind is declared.**

1. **The gate reads the verdict.** `aet ship gate` resolves the requirement from
   the workflow, as it already did, and satisfies it with the `verify` verdict at
   the canonical evidence path. The working-tree file check is removed rather
   than duplicated.
2. **Only `verify` is re-checked at ship.** Every other kind is enforced in-run
   by its own stage gate, at the moment the verdict is written. Re-checking them
   at ship would make merging depend on a per-machine reports archive
   (`~/.aet/reports`) that is not in the repository and is not pushed, so a task
   shipped from a different checkout than the one that ran it would be refused
   for evidence that did exist. `verify` is the exception because a critical task
   can reach `awaiting_merge` without having walked the stage that produces it,
   and ship is the last gate before trunk.
3. **Captured artefacts are referenced, not gated on.** Screenshots, response
   bodies and terminal output stay where `aet-verify` writes them; the verdict's
   summary points at them. A JSON verdict is a claim with provenance; a file's
   existence is not.
4. **The producing skill states its verdict obligation.** `aet-verify` submits
   `aet gate submit --stage verify`, as every other checking skill does.
5. **No component invents a second path.** A new artefact requires the workflow
   to declare it and exactly one producer to write it.

## Consequences

- **Easier:** a critical task that ran its verify stage can ship. The pipeline
  has an in-band route to a mergeable state, which it did not have.
- **Easier:** one contract, checked in one way, in two places that already
  agreed about everything except the filename.
- **Harder:** the refusal is now about a verdict a skill must write, so a task
  that skipped the verify stage cannot be waved through by touching a file. The
  recovery is to run `aet-verify`, which is the intended route.
- **Bounded on purpose:** ship still does not re-check qa, review, cso, or
  sync-docs. Their gates already fired in-run; making trunk access depend on a
  local archive surviving would trade one unsatisfiable gate for another.
- **Migration:** a project that satisfied the old gate with a hand-written
  `.agents/verify/<task-id>-evidence.md` must submit a verdict instead. The file
  is no longer read.

## Alternatives Considered

**Keep the markdown artefact and make the skill write it.** Rejected: it keeps
two artefacts for one kind, and the one the gate would read carries no schema,
no provenance, and no pass/fail — only existence, which is why an empty file
satisfied it.

# Projections Fail Open; Storage Fails Closed

## Status

Accepted.

## Context

The toolkit's kernel rule is fail-closed: missing evidence, missing answer, closed stdin, or a storage write failure produces a failure outcome, never an implicit pass (see `docs/CONVENTIONS.md` and the enforcement-walls PRD). This rule exists because the ledger is the source of truth and must not advance on an uncertain write.

Projections are different. A projection is a one-way mirror of state onto an external surface such as GitHub Issues. The external surface is not in the trust path: AET never reads it back, and a stale or missing mirror does not change what AET believes the state to be. If a projection failure were treated as a command failure, a dead `gh` token, network outage, or API rate limit would halt the factory for a mirror.

The risk of flipping the rule is that a quietly broken projection rots the board until someone notices. The rule therefore needs to be bounded: fail-open applies only to projection writes, only inside the projection dispatcher, and must always warn on stderr so drift is discoverable.

## Decision

Projection writes **fail open**; storage writes remain **fail closed**. This is the one sanctioned inversion of the kernel fail-closed rule, and it is scoped to the projection dispatcher.

1. **The projection dispatcher fans out to configured projections after a successful state write.** It never runs before the state write, and it never participates in the state-write transaction.
2. **A projection failure is caught, warned, and swallowed.** The command exits zero. The warning names the projection type, the operation, and the cause.
3. **Storage failures remain fail-closed.** A git-refs write failure, JSON write failure, or any other storage failure still raises and fails the command. Fail-open does not leak into storage.
4. **Drift is discoverable.** The `aet reconcile` command reports projection drift (missing issue, wrong label, hand-closed issue) and is dry-run by default.
5. **The dispatcher enforces the boundary, not individual projection implementations.** Projection backends raise normally on failure; the dispatcher is responsible for catching and warning. This prevents any single projection from accidentally failing a command or, conversely, from silently ignoring its own errors.

## Consequences

- **Easier:** A GitHub outage or expired token cannot block a status transition, closure, or scheduling decision.
- **Easier:** The board is a convenience; the ledger is the truth. The system remains usable without any projection configured.
- **Easier:** Adding a new projection type does not require re-implementing fail-open logic; the dispatcher owns it.
- **Harder:** A persistent projection failure can leave the board silently out of date. Mitigated by the reconcile command and by the warning on every failed projection write.
- **Harder:** Tests must verify both that projection failures are swallowed and that storage failures are not. The boundary is load-bearing.

## Alternatives Considered

1. **Fail-closed for projections too.** Rejected: it makes the factory dependent on a mirror, which contradicts the goal of keeping AET usable with no forge and with a dead token.
2. **Async projection queue with retries.** Rejected: it adds a durable queue for an optional, non-trust-path surface. The simpler warn-and-swallow model satisfies the requirement.
3. **Skip projections silently on failure.** Rejected: swallowed failures must still warn; otherwise drift is invisible and the board quietly rots.

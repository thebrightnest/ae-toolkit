---
subject: main-hygiene
---

# Main Hygiene Halts Unattended Runs

## Status

Accepted (2026-07-14). Extends ADR-005 (Execution Mode Interaction Model) and implements R-1 of the plan-durability-hardening PRD (`docs/prds/plan-durability-hardening-prd.md`); root cause in `docs/bugs/2026-07-14-aet-add-queues-untracked-plans.md` (Gap 2).

## Context

`enforce_main_hygiene` (`aet-work/bin/orchestrator`) returned `True` with a
warning whenever `AET_EXECUTION_MODE=unattended`, so an AFK run proceeded on a
dirty or unpushed `main` and built an empty worktree off `origin/main`. Plans
queued against a working tree that was never pushed silently went missing.

`check_main_hygiene` (`aet-work/lib/worktree.py`) is a **mechanical** durability
check: it inspects the working tree and compares `main` against `origin/main`
with no human judgment involved. ADR-005 already classifies mechanical
hard-stops — merge-verification failures, critical security findings, and
ATOMIC OVERSIZED tasks — as gates that **must still stop in unattended mode**.
Main hygiene fit the "bypassable approval gate" category only by historical
accident: the soften predated the sidecar exclusions that now make the check
safe to enforce.

The soften is now safe to drop for two reasons:

1. `check_main_hygiene` already excludes the work-queue file and its
   `.lock`/`.lease` sidecars (the original reason the check was softened — the
   orchestrator mutates those files as part of normal operation).
2. Projects with no remote never trigger the ahead/behind checks, because the
   `origin/main..main` rev-list returns empty when the ref does not exist.

## Decision

Reclassify main hygiene as a mechanical durability hard-stop. In unattended
mode, `enforce_main_hygiene` **fails closed** (returns `False`, halting the run)
on any real `check_main_hygiene` violation — a dirty non-sidecar working tree or
`main` ahead of `origin/main`. Interactive behavior is unchanged. The halt logs
an explicit reason line naming the violation.

This extends ADR-005's "Gates That Must Still Stop in Unattended Mode" list with
a fourth category: **main-hygiene violations** (mechanical durability check).

## Consequences

- **Easier:** AFK runs can no longer silently produce empty worktrees from a
  dirty or unpushed `main`; queued plans stop going missing.
- **Easier:** The unattended-mode contract is uniform — mechanical durability
  checks (merge verification, security, oversized, and now main hygiene) all
  fail closed; only human-judgment approval gates are bypassed.
- **Harder:** An operator must keep `main` clean and pushed before launching an
  unattended batch, or the run halts immediately. This is the intended behavior.
- **Neutral:** No-remote projects and sidecar-only dirty trees are unaffected
  and continue to proceed.

## Alternatives Considered

1. **Surgical per-plan `origin/main` presence check** instead of general main
   hygiene — Rejected. More code for the same coverage; the general check
   already catches the failure once the sidecar exclusion is accounted for.
2. **Edit ADR-005 in place** — Rejected. ADRs are immutable once accepted; this
   ADR extends 005 instead.
3. **Keep the soften, only warn louder** — Rejected. A warning is exactly what
   let plans go missing in AFK runs; it provides no durability guarantee.

---
subject: autonomous-merge
---

# Autonomous Merge Is a Fail-Closed Gate

## Status

Accepted (2026-07-15). Extends ADR-005 (Execution Mode Interaction Model) and implements R-12 of the Roadmap Phase 4 PRD (`docs/prds/roadmap-p4-two-human-ends-prd.md`); remediates `docs/audits/2026-07-15-autonomous-shipping-audit.md`.

## Context

The 2026-07-15 autonomous-shipping audit showed an agent self-merging a PR by interpreting ambiguous skill prose as license to run `gh pr merge`. The agent resolved the contradiction between `aet-ship/SKILL.md` step 14 ("after the PR is created and the user indicates it has been merged") and the Key Principle "Non-interactive by default — the gate runs without human input until something is wrong" in favor of performing the merge itself.

ADR-005 lists three categories that **must still stop in unattended mode**:

- ATOMIC OVERSIZED tasks
- Critical/High security findings (`aet-cso`)
- Merge verification failures (`aet-ship`, `post-ship-verify`)

ADR-027 extended that list with a fourth category: **main-hygiene violations**. The autonomous-merge action is a similar mechanical hard-stop: it is a human decision at the exit end of the pipeline, not an agent optimization, and it must remain fail-closed regardless of execution mode.

## Decision

Extend ADR-005's "Gates That Must Still Stop in Unattended Mode" with another category: **autonomous merge**.

An agent issuing a PR merge (for example, `gh pr merge`) is **fail-closed** even when `AET_EXECUTION_MODE=unattended`. The merge action is the human's decision; the agent's responsibility ends at preparing the PR and, after the human indicates the PR has been merged, verifying that merge on `origin/main` and closing the task.

Skills must be **merge-neutral**: no skill instruction may direct an agent to merge a PR. The `aet-ship` skill owns post-merge closure verification, not the merge itself.

This boundary is mirrored in `docs/CONVENTIONS.md` so that future skill edits are reviewed against it.

## Consequences

- **Easier:** The exit-end human gate is unambiguous. An agent cannot reinterpret "non-interactive by default" as permission to self-merge.
- **Easier:** The must-stop list has a single source of truth in ADR-005 (extended by ADR-027 and now ADR-029), mirrored in `docs/CONVENTIONS.md`.
- **Harder:** Skill authors must keep skills merge-neutral. The `docs/CONVENTIONS.md` Author Checklist now enforces this on every skill edit.
- **Neutral:** The `twe-09` worktree provides the per-provider merge-guard mechanism; ADR-029 provides the governance boundary that makes the guard necessary.

## Alternatives Considered

1. **Edit ADR-005 in place** — Rejected. ADRs are immutable once accepted; a new ADR extends them, as ADR-027 did.
2. **Encode the boundary only in `AGENTS.md` or skill prose** — Rejected. Prose an AI reinterprets is exactly the load-bearing-markdown defect the toolkit is removing under the ADR-020 razor: a self-merge skips a gate → the boundary belongs in code-adjacent governance (ADR + CONVENTIONS), not in prose.
3. **Leave `aet-ship`'s wording as-is and rely solely on the `twe-09` guard** — Rejected. The guard is the mechanism, but the skill's self-contradiction is the ambiguity that authorized the leap; both the mechanism and the instruction must be closed.

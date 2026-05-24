# PRD: Execution Mode Interaction Model

## Overview

Introduce a formal execution-mode system across the AE Toolkit so that skills know whether they are running in an interactive session (human present) or unattended orchestration (background AFK loop). This replaces the ad-hoc `AET_ORCHESTRATOR=1` env var with a documented, convention-driven architecture that every skill with human-judgment gates must respect.

## Goals

- **Unified model:** Every skill uses the same mechanism to detect execution mode — no one-off hacks.
- **Secure default:** Interactive mode (default) always enforces approval gates. Unattended mode never silently skips gates; it explicitly bypasses them with audit logging.
- **Orchestrator compatibility:** `aet-work run` can spawn subagents that execute end-to-end without hanging on approval prompts.
- **Agent-agnostic:** The mechanism works for any CLI runtime (Kimi, Claude, Aider, etc.).

## Non-Goals

- Adding new orchestrator features (parallel execution, retry logic, etc.) — out of scope.
- Changing how `--print` or `--yolo` work at the CLI level — we work within existing CLI constraints.
- Removing approval gates from interactive mode — gates remain mandatory.

## User Stories

- As a developer running `aet-work run` overnight, I want queued tasks to complete without hanging on approval prompts so that the AFK loop actually produces code.
- As a developer running `aet-pipeline-implement` directly, I want the agent to ask "Approve to proceed?" before editing files so that I retain control.
- As a skill author, I want a clear convention for handling unattended mode so that my skill works correctly in both interactive and orchestrated contexts.

## Acceptance Criteria

- [ ] All skills with interactive approval gates detect execution mode via the standard mechanism.
- [ ] In unattended mode, skills log the bypass ("Orchestrator mode — skipping interactive approval") for auditability.
- [ ] In interactive mode, skills enforce hard gates exactly as before.
- [ ] `aet-work run` sets the execution-mode signal automatically; no manual user action required.
- [ ] `docs/CONVENTIONS.md` documents the execution-mode pattern for future skill authors.
- [ ] An ADR captures the architectural decision and trade-offs.

## Technical Notes

### Execution Mode Contract

```
Environment variable: AET_EXECUTION_MODE
Values:
  - unset or "interactive"  → Default. Hard gates enforced.
  - "unattended"            → Orchestrator/background mode. Gates bypassed with logging.
```

The orchestrator template (`aet-work/references/orchestrator-template.sh`) exports `AET_EXECUTION_MODE=unattended` before invoking the CLI. Skills check this variable.

**Rationale for renaming from `AET_ORCHESTRATOR`:**

- `AET_ORCHESTRATOR=1` is boolean and tied to a specific tool (`aet-work`).
- `AET_EXECUTION_MODE=unattended` is enum-based, descriptive, and generalizes to any future orchestrator or CI system.

### Gate Bypass Protocol (Unattended Mode)

When a skill detects `AET_EXECUTION_MODE=unattended` at a hard gate:

1. **List scope.** Still enumerate intended files and magnitude (audit trail).
2. **Log bypass.** Print exactly: `🤖 Unattended mode (AET_EXECUTION_MODE=unattended) — skipping interactive approval. Proceeding with: ~N files, ~M lines changed.`
3. **Continue.** Proceed to the next step; do not ask the user.

### Gates That Must Still Stop in Unattended Mode

Not all gates should be bypassed. The following categories **must** still halt execution even in unattended mode:

- **ATOMIC OVERSIZED tasks** — No human available to approve scope override. Hard stop with non-zero exit code.
- **Critical security findings** (aet-cso Critical/High) — Unattended mode should not auto-approve security risks. Stop and require human review.
- **Merge verification failures** (aet-ship, post-ship-verify) — Mechanical check, not a judgment call. Can run unattended, but failures are hard stops.

### Skills Requiring Updates

| Skill                  | Gate Location                         | Unattended Behavior                 |
| ---------------------- | ------------------------------------- | ----------------------------------- |
| aet-implement          | Step 1 approval checkpoint            | Bypass with logging                 |
| aet-implement          | Pre-flight ATOMIC OVERSIZED           | Hard stop                           |
| aet-pipeline-implement | Step 0 approval checkpoint            | Bypass with logging                 |
| aet-pipeline-implement | Step 4 aet-review architecture issues | Hard stop                           |
| aet-pipeline-implement | Step 5 aet-cso Critical/High findings | Hard stop                           |
| aet-ship               | Merge verification                    | Run unattended; failure = hard stop |

## Open Questions

1. Should we add a `--mode unattended` CLI flag to agent CLIs in addition to the env var? (Future — depends on CLI support.)
2. Should the orchestrator support a "dry-run" mode where it lists what it would do without executing? (Future feature.)

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_

## Risks

| Risk                                         | Mitigation                                                                                                                        |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Skill author forgets to check execution mode | Add linter rule in `scripts/validate-skills.sh` to flag skills with "Approve to proceed?" that don't mention `AET_EXECUTION_MODE` |
| Unattended mode bypasses too many gates      | Explicit whitelist: only approval checkpoints are bypassed; security/architecture/oversized gates remain hard stops               |
| Env var not propagated to sub-sub-agents     | Document that any process that spawns an agent CLI must forward `AET_EXECUTION_MODE`                                              |

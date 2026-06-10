# AE Toolkit Pipeline — Canonical Stage State Machine

Single source of truth for skill order, stage transitions, and completion-protocol pointers.

## Stage Order

```
discover → plan → design → validate → prime → implement → qa → review → secure → sync → ship → evolve
```

Execution order in pipelines:

- **Planning**: discover → plan → validate-scope → (optional: validate-ui)
- **Implementation**: implement → qa → review → (conditional: cso) → (conditional: sync-docs) → ship
- **Post-ship**: post-ship-verify
- **Evolution**: evolve (continuous, after any cycle)

## Completion-Protocol Graph

| Skill                    | Completes At                        | Valid Next Steps                     |
| ------------------------ | ----------------------------------- | ------------------------------------ |
| `aet-discover`           | `brief-validated`                   | `aet-plan`                           |
| `aet-plan`               | `prd-approved` / `plan-draft`       | `aet-validate-scope`                 |
| `aet-validate-scope`     | `scope-validated` / `plan-approved` | `aet-pipeline-implement`, `aet-work` |
| `aet-tdd`                | `tdd-complete`                      | `aet-implement`                      |
| `aet-implement`          | `implemented`                       | `aet-qa`                             |
| `aet-qa`                 | `qa-complete`                       | `aet-review`                         |
| `aet-review`             | `reviewed`                          | `aet-cso`, `aet-sync-docs`           |
| `aet-cso`                | `secure`                            | `aet-sync-docs`, `aet-ship`          |
| `aet-sync-docs`          | `synced`                            | `aet-ship`                           |
| `aet-pipeline-implement` | `synced`                            | `aet-ship`, `post-ship-verify`       |
| `aet-ship`               | `shipped`                           | `post-ship-verify`                   |
| `aet-work`               | —                                   | `aet-pipeline-implement` (per task)  |

## Trigger Uniqueness Rule

No two skills may share an exact trigger phrase inside their `description:` frontmatter.
Trigger phrases are quoted strings following `"Triggers on requests like"` or `"Triggers on"`.

## Preamble Template Rule

Skills that declare a `Shared Preamble` section must include at minimum:

- `BRANCH`
- `REPO_STATE`
- `AGENTS_MD`
- `LEARNINGS`
- `ACTIVE_PRD_STAGE`
- `ACTIVE_PLAN_STAGE`

Optional additional fields are permitted (e.g., `ACTIVE_PLAN`, `LAST_PIV`, `TEST_SETUP`).

# AE Toolkit Pipeline Definition

This document is the single source of truth for the canonical stage state machine, skill trigger phrases, completion protocols, and work-class routing.

Any skill that references stages, next steps, or triggers must stay consistent with this doc. The `validate-skills.sh` script enforces this mechanically.

---

## Stage State Machine

### Planning Pipeline

| Stage             | Set By                    | Next Step                                         |
| ----------------- | ------------------------- | ------------------------------------------------- |
| `idea`            | Human or `aet-discover`   | `aet-plan` or `aet-pipeline-plan`                 |
| `prd-draft`       | `aet-plan` → `create-prd` | Human review → `prd-approved` or revise           |
| `prd-approved`    | Human approval            | `aet-validate-scope` (optional `aet-validate-ui`) |
| `scope-validated` | `aet-validate-scope`      | `aet-pipeline-implement` or `aet-implement`       |
| `ui-validated`    | `aet-validate-ui`         | `aet-pipeline-implement` or `aet-implement`       |

### Implementation Pipeline

| Stage           | Set By                    | Next Step                                            |
| --------------- | ------------------------- | ---------------------------------------------------- |
| `plan-approved` | Human approval of plan.md | `aet-tdd`                                            |
| `tdd-complete`  | `aet-tdd`                 | `aet-implement`                                      |
| `implemented`   | `aet-implement`           | `aet-qa`                                             |
| `qa-complete`   | `aet-qa`                  | `aet-review`                                         |
| `reviewed`      | `aet-review`              | `aet-cso` (if security-sensitive) or `aet-sync-docs` |
| `secure`        | `aet-cso`                 | `aet-sync-docs`                                      |
| `synced`        | `aet-sync-docs`           | `aet-ship`                                           |
| `merged`        | `aet-ship` + human merge  | `post-ship-verify` or done                           |

### Terminal States

- `merged` — pipeline complete, branch on `origin/main`
- `archived` — plan abandoned (human decision)

---

## Trigger Phrases

Each trigger phrase must be **unique** across the toolkit. If two skills claim the same phrase, routing is ambiguous.

### Planning

| Skill | Canonical Triggers ||-------|-------------------|| `aet-discover` | "discover this idea", "validate demand", "is this worth building", "customer interview" |
| `aet-plan` | "plan this feature", "create a PRD", "break this into tickets", "help me design" |
| `aet-pipeline-plan` | "pipeline plan this", "run the full planning flow", "plan and validate this feature" |
| `aet-validate-scope` | "validate this plan", "scope check", "does this plan contradict anything" |
| `aet-validate-ui` | "validate UI", "check UI coverage", "UI/UX review this plan", "with UI" (modifier) |

### Implementation

| Skill | Canonical Triggers ||-------|-------------------|| `aet-tdd` | "write tests first", "use TDD", "red-green-refactor", "test-first" |
| `aet-implement` | "implement this plan", "execute the plan", "build this feature", "code this up" |
| `aet-pipeline-implement` | "pipeline implement", "run the full implementation flow", "implement and test and review", "full pipeline on this plan" |
| `aet-qa` | "run QA", "test everything", "quality check", "regression test" |
| `aet-review` | "review this code", "code review", "staff review", "architectural review" |
| `aet-cso` | "security audit", "CSO check", "security review", "audit this diff" |
| `aet-sync-docs` | "sync docs", "update PRD", "document what was built", "divergence summary" |
| `aet-ship` | "ship this", "merge this", "open a PR", "prepare for merge" |

### Operations

| Skill | Canonical Triggers ||-------|-------------------|| `aet-prime` | "prime the session", "load context", "start session", "where were we" |
| `aet-work` | "run the queue", "pick next task", "what's next", "what's unblocked", "run all tasks" |
| `aet-evolve` | "evolve this", "retrospective", "lessons learned", "improve the process" |
| `aet-release-prep` | "prepare release", "update changelog", "bump version", "release notes" |
| `aet-setup` | "setup this project", "bootstrap repo", "add guardrails", "init AE toolkit" |

### Rules

1. **No overlap.** If a phrase maps to two skills, disambiguate or retire one.
2. **Specific beats generic.** "plan this feature" → `aet-plan`; "plan and validate this feature" → `aet-pipeline-plan`.
3. **Modifiers are not standalone triggers.** "with UI" only activates `aet-validate-ui` when attached to a planning request.

---

## Completion Protocol Graph

```
aet-discover
    → (idea validated) → aet-plan / aet-pipeline-plan

aet-plan
    → (PRD approved) → aet-validate-scope [→ aet-validate-ui]

aet-pipeline-plan
    → (scope-validated) → aet-pipeline-implement

aet-pipeline-implement
    Step 1: aet-tdd
        → (tests exist and fail for right reasons) → tdd-complete
    Step 2: aet-implement
        → (all tests pass, lint/type OK) → implemented
    Step 3: aet-qa
        → (coverage maintained, no new bugs) → qa-complete
    Step 4: aet-review
        → (no critical architecture issues) → reviewed
    Step 5: aet-cso (conditional)
        → (no Critical/High findings) → secure
    Step 6: aet-sync-docs (conditional)
        → (divergences documented) → synced
    → aet-ship
        → (PR merged) → merged
```

---

## Work-Class Routing Table

| Work Class | Definition | Pipeline | Skips ||------------|-----------|----------|-------|| `critical` | Security, data loss, revenue-impacting bug | Full pipeline (all steps) | Nothing |
| `standard` | New feature, refactor, visible improvement | Full pipeline | Nothing |
| `quickfix` | Typo, copy change, one-liner fix | aet-implement → aet-qa → aet-ship | aet-tdd, aet-review (post-hoc OK) |
| `docs-only` | README, comments, ADR, no code change | aet-implement (doc edits) → aet-ship | aet-tdd, aet-qa, aet-review |
| `spike` | Research, proof of concept, time-boxed | aet-plan → aet-implement (spike code) → aet-review (scope only) | aet-tdd, aet-qa, aet-cso |

---

## Change Control

- **Add a stage:** Update this doc first, then update the skill that sets it, then update `validate-skills.sh`.
- **Add a trigger phrase:** Update this doc, then update the skill's `description:` frontmatter.
- **Remove a skill:** Update this doc, then update the completion protocol graph, then update `validate-skills.sh`.

---

_Last updated: 2026-06-10_
_Validated by: validate-skills.sh_

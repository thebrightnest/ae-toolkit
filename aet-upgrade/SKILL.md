---
name: aet-upgrade
description: Dependency and framework upgrade planning with breaking-change analysis and risk mapping. Use when bumping a dependency by major or minor version, upgrading a framework, or evaluating whether an upgrade affects your codebase. Triggers on requests like "upgrade Laravel," "bump npm package," "plan dependency upgrade," or "evaluate breaking changes."
---

# aet-upgrade

Upgrade planning for agentic engineering. Treats dependency and framework upgrades as a first-class, critical-class work type — not a feature, not a bug, and not something that bypasses governance.

## When to Use

- A dependency or framework needs to be bumped by major or minor version
- You want to know exactly which breaking changes affect your codebase before starting
- You need a risk-mapped plan with evidence before executing an upgrade
- The upgrade touches infrastructure, data models, or auth-adjacent code

## Before You Start

Before executing any command in this skill, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `DEPENDENCY` — name and target version of the dependency being upgraded
- `CURRENT_VERSION` — currently installed version (from lockfile, package.json, composer.lock, etc.)
- `PACKAGE_MANAGER` — npm, composer, pip, cargo, etc.
- `SMOKE_STATUS` — result of the most recent foundation smoke check (pass / fail / unknown)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

## Commands

### `plan`

Produce a risk-mapped upgrade plan by analyzing the changelog and grepping the codebase for affected patterns.

**Procedure:**

1. **Fetch the upgrade guide or changelog**

   - Locate the official upgrade guide for `CURRENT_VERSION` → `TARGET_VERSION`
   - Prefer the framework's official migration guide over raw changelog
   - If no official guide exists, use the GitHub releases page or changelog file
   - For internal packages with no published changelog, document this gap and proceed with diff-based analysis

2. **Enumerate breaking changes**

   - List every documented breaking change between the two versions
   - Include deprecation removals, signature changes, configuration changes, and behavioral changes
   - Note any new required dependencies or dropped platform support

3. **Grep the codebase for each breaking change**

   - For each breaking change, search the codebase for affected patterns
   - Use `grep`, `rg`, or language-aware search as appropriate
   - Document file paths and line counts for each match
   - If a breaking change has zero matches, note it as "no direct usage found"

4. **Classify risk for each breaking change**

   | Risk       | Criteria                                                                    | Action                                           |
   | ---------- | --------------------------------------------------------------------------- | ------------------------------------------------ |
   | **High**   | Pattern found in production code with no test coverage                      | Requires explicit mitigation plan before upgrade |
   | **Medium** | Pattern found in production code with test coverage, or found in tests only | Standard upgrade path; verify tests pass after   |
   | **Low**    | Pattern not found in codebase, or found only in docs/comments               | Document and skip; no code changes needed        |

5. **Produce the upgrade plan**

   - Write a markdown plan file: `docs/plans/{ticket}-upgrade-{dependency}.md`
   - Include: dependency name, version range, breaking change checklist with risk ratings, grep evidence, mitigation steps for high-risk items, and smoke test requirements
   - Follow the format in [references/breaking-change-template.md](references/breaking-change-template.md)

6. **Smoke before/after requirement**
   - Before starting the upgrade: run foundation smoke checks. If they fail, fix smoke first — do not upgrade on a broken baseline.
   - After completing the upgrade: run foundation smoke checks again. If they fail, the upgrade is not complete.
   - Document smoke results in the plan footer.

**Rules:**

- Never execute the actual dependency bump (`composer update`, `npm install`) as part of this skill. The skill plans and validates; the bump is executed separately.
- Never skip the grep step. "I don't think we use that" is not evidence.
- If the upgrade guide is ambiguous, search the codebase for both the old and new patterns.

### `verify`

Post-upgrade verification. Run after the dependency has been bumped and code changes applied.

**Procedure:**

1. Run the full test suite
2. Run foundation smoke checks
3. Verify no high-risk breaking changes remain unaddressed
4. Update the plan footer with verification results

## Completion Protocol

After the upgrade plan is produced:

1. Update the plan.md footer:

   ```
   *Stage: plan-approved*
   *Work class: critical*
   *Next step: aet-pipeline-implement*
   ```

2. Print:

   ```
   ✓ Upgrade plan complete.

   Dependency: {name} {current} → {target}
   High-risk breaking changes: {N}
   Medium-risk breaking changes: {N}
   Low-risk breaking changes: {N}

   Next step: run aet-pipeline-implement to execute the upgrade with full governance.
   ```

## Key Principles

- **Upgrades are critical-class work** — they touch the foundation of the application and require the same governance as auth or data model changes.
- **Evidence over intuition** — every risk rating must be backed by grep results, not developer memory.
- **Smoke gates the upgrade** — no upgrade starts on a broken baseline, and no upgrade finishes with broken smoke.
- **Framework-agnostic procedure** — the skill works for npm, composer, pip, cargo, or any package manager with a published changelog.

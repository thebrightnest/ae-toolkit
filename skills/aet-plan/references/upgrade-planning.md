# Upgrade Planning

Use this reference from `aet-plan`'s `plan` command when the ticket is a dependency
or framework upgrade (a major or minor version bump). Upgrades are critical-class
work: they touch the foundation of the application and get the same governance as
auth or data-model changes.

The output is an ordinary queueable plan. Everything in the `plan` procedure still
applies (frontmatter contract, size guardrails, R-trace discipline, self-consistency
lint); this reference adds the upgrade-specific analysis and plan-shaping rules.

## Inputs

- `DEPENDENCY` — name and target version of the dependency being upgraded
- `CURRENT_VERSION` — installed version (from the lockfile or manifest)
- `PACKAGE_MANAGER` — npm, composer, pip, cargo, etc.

## Analysis

1. **Find the upgrade guide or changelog**
   - Locate the official upgrade guide for `CURRENT_VERSION` → target version.
   - Prefer the framework's migration guide over the raw changelog.
   - With no official guide, use the GitHub releases page or changelog file.
   - For internal packages with no published changelog, record the gap and fall back
     to diff-based analysis.
2. **List the breaking changes**
   - Every documented breaking change between the two versions: deprecation removals,
     signature changes, configuration changes, and behavioral changes.
   - New required dependencies and dropped platform support.
3. **Search the code for each breaking change**
   - Use `grep`, `rg`, or language-aware search for each affected pattern.
   - Record file paths and match counts. Zero matches is recorded as "no direct usage
     found".
   - If the guide is ambiguous, search for both the old and the new pattern.
   - Never skip this step. "I don't think we use that" is not evidence.
4. **Rate the risk of each breaking change**

   | Risk       | Criteria                                                                    | Action                                           |
   | ---------- | --------------------------------------------------------------------------- | ------------------------------------------------ |
   | **High**   | Pattern found in production code with no test coverage                      | Requires explicit mitigation plan before upgrade |
   | **Medium** | Pattern found in production code with test coverage, or found in tests only | Standard upgrade path; verify tests pass after   |
   | **Low**    | Pattern not found in codebase, or found only in docs/comments               | Document and skip; no code changes needed        |

   A Medium-risk change whose fix turns out to be non-trivial is treated as High.

## Plan-Shaping Rules

- Frontmatter declares `work_class: critical`. Under the `critical-only` default this
  turns `verify` on, so the pipeline enforces the before-and-after smoke check.
- Frontmatter declares `pipeline: standard` or `full` (dependency risk override); never
  `minimal`.
- One task per High-risk breaking change, each naming its mitigation and the test that
  covers the affected behavior before the bump.
- Validation steps include the project's smoke command both before and after the bump.
  A failing baseline is fixed first; no upgrade starts on broken smoke, and no upgrade
  is complete with broken smoke.
- The plan never runs the bump itself during planning (`composer update`,
  `npm install`); the bump is a task in the plan, executed by the implementation stage.

## Breaking-Change Inventory

Add this section to the plan body, after the task list.

```markdown
## Breaking-Change Inventory

- **Dependency:** `{name}`
- **Current:** `{version}`
- **Target:** `{version}`
- **Package manager:** `{npm|composer|pip|cargo|...}`

### {N}. {Short name}

**Description:** {What changed and why it is breaking.}

**Grep evidence:**

    {The search command and its output.}

**Risk:** **{High|Medium|Low}** — {Justification against the risk table.}

**Mitigation:**

- {Specific code change or verification step.}

## Smoke Results

- **Before upgrade:** {Pass / Fail} ({date})
- **After upgrade:** {Pass / Fail / Pending}
```

Repeat the numbered entry for each breaking change. The plan's normal Rollback section
names the manifest and lockfile to revert.

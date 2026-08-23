# Breaking-Change Analysis Template

Use this template when producing an upgrade plan with `aet-upgrade plan`.

## Header

```markdown
# Plan: Upgrade {Dependency} {Current} → {Target}

## Context

- **Dependency:** `{name}`
- **Current:** `{version}`
- **Target:** `{version}`
- **Package manager:** `{npm|composer|pip|cargo|...}`
- **Ticket:** `{ticket-id}`
```

## Breaking Change Entry

Repeat this section for each breaking change:

````markdown
### {N}. {Short name}

**Description:** {What changed and why it is breaking.}

**Grep evidence:**

```bash
{Paste the grep command and output.}
```
````

**Risk:** **{High|Medium|Low}** — {Justification referencing the risk classification criteria.}

**Mitigation:**

- {Specific code change or verification step.}
- {Specific code change or verification step.}

````

## Smoke Results

```markdown
## Smoke Results

- **Before upgrade:** {Pass / Fail} ({date})
- **After upgrade:** {Pass / Fail / Pending}
````

## Rollback

```markdown
## Rollback

{Specific files to revert and confirmation step.}
```

## Footer

No footer. Plan files are transient working copies (gitignored); stage and
work class are recorded on the task record by code, not in the plan file.

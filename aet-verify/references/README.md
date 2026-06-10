# References for aet-verify

## Evidence File Naming Convention

All evidence files live in `/tmp/aet-reports/{task-id}/evidence/`.

Format:

```
{mode}-{YYYYMMDD}-{HHMMSS}-{slug}.{ext}
```

- `mode`: `foundation` | `feature` | `reproduction`
- `slug`: short description of what was verified (kebab-case)
- `ext`: `json`, `txt`, `png`, `har`, `md`

Examples:

- `feature-20260610-143022-login-200.json`
- `foundation-20260610-090000-smoke.txt`
- `reproduction-20260610-160515-delete-hang.png`

## Metadata Header Format

Text evidence files (.json, .txt, .md) must begin with:

```
---
mode: foundation|feature|reproduction
task: {task-id}
tool: curl|playwright|cli|script
timestamp: {ISO-8601}
---
```

This header is stripped before parsing if the file is consumed by another tool.

## Integration with aet-qa Report Format

When `aet-qa` produces a QA report at `/tmp/aet-reports/{task-id}/qa-report.md`, `aet-verify` appends an **Evidence** section:

```markdown
## Evidence

| Check                      | Tool       | Result | Artifact                                     |
| -------------------------- | ---------- | ------ | -------------------------------------------- |
| POST /api/login            | curl       | PASS   | feature-20260610-143022-login-200.json       |
| Project delete (100 tasks) | Playwright | FAIL   | reproduction-20260610-160515-delete-hang.png |
```

If no QA report exists, `aet-verify` creates one with the Evidence section as the primary content.

## Smoke Check Scaffold

Projects should define smoke checks in one of these locations:

1. `make smoke` — preferred; runs all substrate checks
2. `.agents/smoke/` — directory of executable scripts; `aet-verify` runs all `*.sh` files
3. `package.json` script — `npm run smoke`, `pnpm smoke`, `yarn smoke`

A minimal smoke script should verify:

- Application boots without error
- Auth flow (login + session creation)
- One CRUD cycle on a core entity
- Dev service health (database, cache, queue)

## Work-Class Conditional Routing

| Work class | Foundation | Feature   | Reproduction |
| ---------- | ---------- | --------- | ------------ |
| trivial    | skip       | skip      | if requested |
| normal     | optional   | skip      | if requested |
| critical   | mandatory  | mandatory | if requested |

Foundation mode is "once per session" for all developers, regardless of work class.

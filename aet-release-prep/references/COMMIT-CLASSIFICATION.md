# Commit Classification Reference

## Conventional Commit Prefixes

The script recognizes these prefixes (case-insensitive):

| Prefix                    | Type     | Version Impact |
| ------------------------- | -------- | -------------- |
| `feat:` or `feature:`     | feature  | minor          |
| `fix:` or `bugfix:`       | fix      | patch          |
| `docs:`                   | docs     | patch          |
| `chore:`, `build:`, `ci:` | chore    | patch          |
| `refactor:`               | refactor | patch          |
| `style:`                  | style    | patch          |
| `test:`                   | test     | patch          |
| `perf:`                   | perf     | patch          |

Optional scope is supported: `feat(scope): description`

## Breaking Change Detection

A commit is classified as **breaking** if either:

1. The body contains `BREAKING CHANGE` (any case)
2. The subject uses the `!` suffix: `feat!:`, `fix!:`, etc.

Breaking changes always trigger a **major** version bump.

## Keyword Fallbacks

If no conventional prefix matches, the subject is checked for keywords:

| Keyword pattern         | Type        | Examples                            |
| ----------------------- | ----------- | ----------------------------------- |
| Starts with `add`       | feature     | "Add login page"                    |
| Contains `new feature`  | feature     | "Implement new feature for exports" |
| Starts with `implement` | feature     | "Implement OAuth flow"              |
| Starts with `fix`       | fix         | "Fix navigation bug"                |
| Contains `bug`          | fix         | "Resolve caching bug"               |
| Starts with `update`    | improvement | "Update dependencies"               |
| Starts with `improve`   | improvement | "Improve load times"                |
| Starts with `remove`    | removal     | "Remove legacy API"                 |
| Starts with `delete`    | removal     | "Delete unused components"          |

Everything else falls to **other** (patch by default).

## Classification Precedence

1. Breaking change indicators (highest priority)
2. Conventional commit prefix
3. Keyword fallback
4. Default to `other`

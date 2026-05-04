# Git as Memory

## What to Read

### Recent Commits (Last 5–10)

- **Why:** Reveals current coding style, file organization, testing conventions
- **How:** `git log --oneline -10` then read full diffs for commits touching similar areas
- **Look for:** Conventional commit prefixes, naming patterns, test file locations

### Commit Messages

- **Pattern analysis:** Are they using `feat:`, `fix:`, `refactor:`? Follow the same style.
- **Scope indicators:** Do messages include scope like `feat(auth):` or `fix(api):`?
- **Body style:** Do they include breaking change notes or issue references?

### File History

- **Why:** If modifying an existing file, read its last 2–3 commits to understand evolution
- **How:** `git log -p --follow -3 -- path/to/file`
- **Watch for:** Refactoring patterns, recent bug fixes, performance optimizations

## What NOT to Read

- **Ancient history (>30 commits back)** — conventions may have changed
- **Merge commits** — usually noise unless investigating a specific conflict
- **Automated commits** (lint fixes, version bumps) — no human decision to learn from

## Interpreting Patterns

| Pattern Seen                      | What It Means                                             |
| --------------------------------- | --------------------------------------------------------- |
| Test files co-located with source | Follow this pattern; don't create separate `tests/` dirs  |
| Factory usage in tests            | Use factories; don't hardcode test data                   |
| Explicit error types              | Match the error handling style (custom errors vs generic) |
| Structured logging                | Use the same log shape (timestamp, level, name, message)  |

# Example: Patch Release

**Scenario:** A bug fix and a docs update were merged. No new features.

## User Request

> "Cut a patch release"

## Script Output

```json
{
  "lastTag": "v1.1.0",
  "currentVersion": "1.1.0",
  "versionSource": "git-tag",
  "commitCount": 2,
  "commits": [
    {
      "hash": "m3n4o5p6",
      "type": "fix",
      "subject": "fix: prevent pre-commit hook from blocking on staged binaries"
    },
    {
      "hash": "q7r8s9t0",
      "type": "docs",
      "subject": "docs: clarify branch lifecycle policy in CONVENTIONS"
    }
  ],
  "suggestedBump": "patch",
  "nextVersion": "1.1.1"
}
```

## Agent Actions

1. **Confirm bump:** User agrees patch (1.1.0 → 1.1.1)
2. **Update CHANGELOG.md:**

   ```markdown
   ## [1.1.1] — 2026-06-02

   ### Fixed

   - Pre-commit hook no longer blocks when large binaries are staged

   ### Documentation

   - Clarified branch lifecycle policy in CONVENTIONS.md

   ---
   ```

3. **Update PRODUCT.md:**
   - Add "What's New in v1.1.1" with 1 bullet (the bug fix benefit)
   - Docs updates typically do not appear in "What's New" unless they correct user-facing instructions
4. **Bump version:** Note `v1.1.1` for the user to tag manually

## Result

User reviews, commits, tags `v1.1.1`, and pushes.

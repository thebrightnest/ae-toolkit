# Example: Minor Release

**Scenario:** Two new skills and a UX improvement were merged since the last release.

## User Request

> "Prepare the next release"

## Script Output

```json
{
  "lastTag": "v1.0.0",
  "currentVersion": "1.0.0",
  "versionSource": "git-tag",
  "commitCount": 3,
  "commits": [
    {
      "hash": "a1b2c3d4",
      "type": "feature",
      "subject": "feat: add aet-release-prep skill for automated release docs"
    },
    {
      "hash": "e5f6g7h8",
      "type": "feature",
      "subject": "feat: add parallel execution support to aet-work"
    },
    {
      "hash": "i9j0k1l2",
      "type": "fix",
      "subject": "fix: resolve queue drift detection false positive"
    }
  ],
  "suggestedBump": "minor",
  "nextVersion": "1.1.0"
}
```

## Agent Actions

1. **Confirm bump:** User agrees minor (1.0.0 → 1.1.0) is correct
2. **Update CHANGELOG.md:**

   ```markdown
   ## [1.1.0] — 2026-06-02

   ### Added

   - `aet-release-prep` skill for automated release preparation
   - Parallel execution support in `aet-work` for concurrent task processing

   ### Fixed

   - Queue drift detection no longer reports false positives on clean queues

   ---
   ```

3. **Update PRODUCT.md:**
   - Add "What's New in v1.1.0" with 2 bullets (the features)
   - Add `aet-release-prep` to the Skills table
   - Update aet-work core feature section to mention parallel execution
4. **Bump version:** Note `v1.1.0` for the user to tag manually (git-tag source)

## Result

User reviews, commits, tags `v1.1.0`, and pushes.

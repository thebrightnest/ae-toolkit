# Edge Cases

## No Tags Exist

If the script reports `lastTag: "(no tags)"`:

1. Ask the user: "No git tags found. What version should this first release be?"
2. Default suggestion: `1.0.0` for initial release, or use the detected `currentVersion`
3. All commits in the repository history are analyzed

## No Commits Since Tag

If no commits exist since the last tag:

1. Inform the user: "There are no commits since vX.Y.Z. Nothing to release."
2. Ask if they want to create the documentation files anyway (e.g., to fix a prior release)
3. If yes, proceed with the current version or a user-specified version

## Missing CHANGELOG.md

If `CHANGELOG.md` does not exist at the repo root:

1. Create it with a header:

   ```markdown
   # Changelog

   All notable changes to this project.

   ---
   ```

2. Add the first release section after the header

## Missing PRODUCT.md

If `PRODUCT.md` does not exist at the repo root:

1. Use the template in `references/PRODUCT-TEMPLATE.md`
2. Populate it based on:
   - The codebase structure
   - Recent commit history (user-facing commits only)
   - Any existing documentation (README, docs/, etc.)
3. Ask the user to review and fill gaps

## Only Internal Commits

If all commits since the last tag are internal (tests, refactors, CI):

1. Suggest a **patch** bump (or skip if the user prefers)
2. In `PRODUCT.md`:
   - Do NOT create a "What's New" section (no user-facing changes)
   - Update any core feature sections only if internal changes altered behavior
3. In `CHANGELOG.md`:
   - Still document the release
   - Group under "Changed" or "Chores" as appropriate

## Merge Commits

Merge commits (subjects starting with `Merge pull request` or `Merge branch`) are classified as `other` by default. The individual commits within the merge are what matter — those are already in the history.

## Reverts

Commits starting with `Revert` or `revert:` are classified based on what is being reverted. A revert of a feature may effectively be a fix. Use judgment and confirm with the user.

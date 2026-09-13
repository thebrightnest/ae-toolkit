# Edge Cases

## Tags Exist But None Are Reachable

`unreachableTags` is non-empty while `reachableTags` is empty. The tags arrived
with a vendored import, or sit on a line of history that was abandoned by a
rebase or an orphan branch. `git describe` fails outright on this shape.

1. **Do not** use an unreachable tag as the baseline — it is not an ancestor, so
   the diff against it is meaningless.
2. Tell the user which tags were skipped and why, and state the baseline that
   was used instead.
3. Confirm the version to start from. A repo whose own release history begins at
   the import usually starts fresh at `1.0.0`, not at the imported tag.
4. After the release, tag it so the next run resolves cleanly.

## No Baseline At All

`baselineReason` is `no-baseline`: no reachable tag, and no changelog to date
from. The window is the entire history.

1. Say so explicitly before writing anything — `commitCount` is the whole repo.
2. Treat it as a bootstrap run (see below).
3. Set `baseline_ref` in `.agents/aet-config.json` or tag the release afterwards.

## Bootstrap Runs

`bootstrap` is `true` when there is no prior release to append to — no baseline,
or one of the two documents does not exist yet.

1. Seed the missing document(s); `PRODUCT-TEMPLATE.md` has the PRODUCT.md skeleton.
2. Write **one** entry for the whole window, at the altitude the window
   deserves. Three hundred commits with no prior release become a short
   "current state" summary, never three hundred bullets.
3. For PRODUCT.md, describe what the product **does today** — read the codebase
   and README, not just the commit subjects. The commit log of a bootstrap
   window is a poor description of a product.
4. Finish by telling the user to set `baseline_ref` or tag, so run two is
   incremental.

## Dated Projects

`versionScheme` is `dated`. The project deploys continuously and has no version
numbers — `suggestedBump` and `nextVersion` are `null`.

1. Head the changelog entry with `releaseDate`, not a version.
2. **Do not** edit any manifest version, even if one exists. A vestigial
   `version = "0.1.0"` in `pyproject.toml` is not the release version.
3. **Do not** suggest tagging in the summary.
4. If the changelog documents its own inclusion policy, obey it — dated
   changelogs usually carry one.

## No Commits Since the Baseline

`commitCount` is 0.

1. Inform the user: "There are no commits since [baselineRef]. Nothing to release."
2. Ask if they want to update the documents anyway (e.g., to fix a prior release).
3. If yes, proceed with the current version or a user-specified version.

## Missing Changelog

The file at `documents.changelog.path` does not exist (`exists: false`).

1. Create it at that path with a header:

   ```markdown
   # Changelog

   All notable changes to this project.

   ---
   ```

2. Add the first entry after the header.

## Missing PRODUCT.md

The file at `documents.product.path` does not exist.

1. Use the template in `PRODUCT-TEMPLATE.md`.
2. Populate it based on the codebase structure, user-facing commits, and
   existing documentation (README, `docs/`).
3. Ask the user to review and fill gaps.

## Only Internal Commits

Every commit in the window is internal (tests, refactors, CI).

1. Suggest a **patch** bump (or skip the release if the user prefers).
2. In PRODUCT.md:
   - Do NOT create a "What's New" section — there is nothing user-facing
   - Update core feature sections only if internal changes altered behavior
3. In the changelog:
   - Still document the release
   - Group under "Changed" or "Chores" as appropriate

## Merge Commits

Merge commits (`Merge pull request`, `Merge branch`) classify as `other`. The
individual commits within the merge are what matter, and they are already in the
window.

## Reverts

Commits starting with `Revert` or `revert:` are classified from what is being
reverted. A revert of a feature may effectively be a fix. Use judgment and
confirm with the user.

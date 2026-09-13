---
name: aet-release-prep
description: Automate release preparation by analyzing commits since the last release, detecting the project's versioning scheme, suggesting semantic version bumps, and updating CHANGELOG.md and PRODUCT.md. Use when preparing a release, updating changelogs, bumping versions, or keeping product documentation current. Triggers on "prepare release," "update changelog," "release prep," "version bump," or "what's new in this release."
---

# aet-release-prep

Automate release preparation by analyzing git commits since the last release and generating documentation updates.

**Use this for:** Preparing releases, updating changelogs, bumping versions, keeping product documentation current.

---

## When to Use

- The user says "prepare release," "update changelog," "release prep," or "version bump"
- The user asks "what's new in this release" or wants to draft release notes
- Before tagging a new version — after features are merged but before the release is published
- When CHANGELOG.md or PRODUCT.md has fallen behind the actual shipped changes

## What This Skill Does NOT Do

- Does not create git tags, push to remote, or publish artifacts
- Does not merge code or create PRs (use `aet-ship` for that)
- Does not run tests or validate code correctness
- Does not enforce that a release must happen after every merge

---

## Step 1: Analyze the Release Window

```bash
aet release-prep
```

Add `--since <ref>` to override where the window starts. The command reads the
optional `release_prep` section of `.agents/aet-config.json` and auto-detects
everything it does not find there — see `references/CONFIG.md`.

Key fields in the JSON output:

| Field | Meaning |
| --- | --- |
| `baselineRef` / `baselineReason` | Where the window starts, and how that was decided |
| `bootstrap` | `true` when there is no prior release to append to — see Step 2 |
| `versionScheme` | `semver-tag`, `semver-file`, or `dated` — drives Steps 4 and 6 |
| `versionSource` / `currentVersion` | Which manifest holds the version, and its value |
| `documents.changelog.path` / `documents.product.path` | Where each document lives |
| `unreachableTags` | Tags that exist but are **not** ancestors of HEAD |
| `commits` / `summary` | Classified commits and per-type counts |
| `suggestedBump` / `nextVersion` | `null` under the `dated` scheme |

**Stop and confirm with the user when any of these hold:**

- `unreachableTags` is non-empty — tags exist that the window ignored. They
  usually arrived with a vendored import or sit on an abandoned line of
  history. Say which ones, and ask whether the baseline is right.
- `baselineReason` is `no-baseline` — the window is the entire history.
- `commitCount` is implausibly large for one release.
- The suggested bump looks wrong for what the commits actually did.

---

## Step 2: Read Before Writing

Read both documents in full before editing either one — `documents.changelog.path`
and `documents.product.path` from Step 1. This is not a formality:

**Match the existing document's convention.** If the changelog groups by
`### Added / ### Changed / ### Fixed`, keep doing that. If it writes a paragraph
per change with the reasoning inline, keep doing that. If it opens with a
"what belongs here" policy section, obey that policy. A release run must never
convert a project's changelog to a different house style — the format templates
below are defaults for a file that has no convention yet, not a target to
migrate toward.

**If `bootstrap` is true**, this is a first run. Do not invent a release
history. Instead:

1. Seed the missing document(s) — `references/PRODUCT-TEMPLATE.md` has the
   PRODUCT.md skeleton.
2. Write **one** entry covering the window, described at the level the window
   deserves. Hundreds of commits with no prior release summarize to a short
   "current state" entry, not a hundred bullets.
3. Tell the user to set `baseline_ref` in `.agents/aet-config.json` (or tag the
   release) so the next run is incremental.

---

## Step 3: Update the Changelog

### CRITICAL: Append-Only Rule

**NEVER replace or modify existing entries.** The changelog is append-only.

1. **Read the entire file first** to understand the existing structure
2. **Insert the new section** between the file header and the first existing entry
3. **Do NOT touch any existing sections** — they are historical records
4. If a section already exists for the target release, UPDATE only that section (do not duplicate)
5. Use the Edit tool for a targeted insert — never rewrite the whole file

### Format

Under `semver-tag` / `semver-file`, head the section with the version:

```markdown
## [X.Y.Z] — YYYY-MM-DD

### Added

- New feature description (from `feat:` commits)

### Changed

- Change description (from `refactor:`, improvements)

### Fixed

- Bug fix description (from `fix:` commits)

---
```

Under `dated`, there is no version to head it with. Use `releaseDate`:

```markdown
## YYYY-MM-DD

**What shipped.** What changed and why it was worth doing.

---
```

### Guidelines

1. **Group commits by type** (Added, Changed, Fixed, Documentation)
2. **Write user-facing descriptions** — translate technical commits into benefits
3. **Include PR/issue references** if mentioned in commit body
4. **Skip internal commits** (CI, build tooling) unless significant
5. **Combine related commits** into single entries when they address the same feature
6. **Verify after editing** — read the file again to confirm all previous entries are still present

---

## Step 4: Update PRODUCT.md

Update the file at `documents.product.path`.

PRODUCT.md is a **product snapshot** for cross-functional teams (Marketing, Sales, Support). It documents features at a user level — not implementation details. Every line should read as **product documentation**, never as a developer changelog.

### CRITICAL: Preserve Existing "What's New" Sections

PRODUCT.md contains a **"What's New"** section per release. These are
**historical records** — treat them exactly like changelog entries.

1. **Read the entire file first** to understand the existing structure
2. **Do NOT delete or modify** any previous "What's New" section
3. **Verify after editing** — read the file again to confirm they are all still present

### Step 4a: Triage Commits — User-Facing vs Internal

Before writing anything, categorize **every commit** from the window into one of two buckets:

| Category        | What belongs here                                                                                                             | Examples                                                                                       |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **USER-FACING** | New features users can see/click, UX changes, new integrations, new shipped skills, bug fixes users were hitting              | "Add Project Assistant skill", "Add chat starter suggestions", "Fix permission queue blocking" |
| **INTERNAL**    | Tests, SDK upgrades, refactors, naming conventions, build/CI, logging, migration internals, dead code removal, dev-only fixes | "Add 173 E2E tests", "Upgrade Agent SDK", "Rename skill prefixes", "Extract shared helper"     |

**Rule of thumb:** If a user wouldn't notice the change while using the app, it's INTERNAL.

### Step 4b: Update Core Feature Sections (Primary Output)

This is the most important part. PRODUCT.md's core feature sections are the **evergreen product documentation** — they describe what the product does today.

**For new user-facing features:**
Add a new section following the established pattern:

```markdown
### Feature Name

What it does — one-sentence summary of the capability.

**Why it matters:** Benefit to the user in plain language.

**Use cases:**

- Concrete scenario 1
- Concrete scenario 2
```

**For enhancements to existing features:**
Update the existing section's description to reflect the **current state**. Rewrite as present-tense documentation, not "we added X" changelog-style.

```markdown
<!-- ✅ GOOD: reads as current documentation -->

### Chat

Start conversations with suggested prompts or type your own...

<!-- ❌ BAD: reads as a changelog entry -->

### Chat

Now includes chat starter suggestions for easier onboarding...
```

**For new integrations or skills:**
Add entries to the relevant tables (Integrations, Skills) following the existing format.

### Step 4c: Update "What's New" Section (Brief Marketing Summary)

Insert a new "What's New" section at the TOP of the "What's New" area (before
existing ones). Head it with `vX.Y.Z` under a semver scheme, or with the
`releaseDate` under `dated`.

**Rules:**

- **Only user-facing changes** from the Step 4a triage — zero internal items
- **3–8 bullets max** — combine related changes, cut ruthlessly
- **Write benefit statements**, not technical descriptions
- **No "plus technical improvements" catch-all** — if it's not user-facing, it doesn't belong

**Good vs bad bullets:**

| ✅ Good (benefit statement)                                     | ❌ Bad (developer changelog)                  |
| --------------------------------------------------------------- | --------------------------------------------- |
| Project Assistant skill for AI-guided project setup             | Added SessionStart hook for context injection |
| Chat starter suggestions to help you begin conversations faster | 173 E2E tests across 6 test suites            |

### Step 4d: Verify

1. **Read the file again** after editing to confirm:
   - All previous "What's New" sections are still present
   - Header version and date are updated
   - Core feature sections are updated for new capabilities
2. **Consumer-focus check:** Read every line you added and ask: _"Does this read as product documentation, or as a developer changelog?"_ If the latter, rewrite or remove it
3. Use the Edit tool for targeted changes — never rewrite the entire file

---

## Step 5: Bump the Version

What to edit depends entirely on `versionScheme`. Do not edit a version string
the scheme does not own.

| `versionScheme` | Action |
| --- | --- |
| `dated` | **Nothing.** The project has no version numbers; the dated entry is the release. Skip to Step 6. |
| `semver-tag` | No file to edit — the git tag _is_ the version (`versionSource` is `git-tag` or `setuptools-scm`). Report `nextVersion` for the user to tag. |
| `semver-file` | Edit the version field in the file named by `versionSource` to `nextVersion`. |

Confirm the bump with the user before applying it. **Always** confirm a major bump.

---

## Step 6: Summary

```markdown
## Release Prep Complete

**Release:** {vA.B.C (patch/minor/major) | YYYY-MM-DD}
**Version scheme:** {semver-tag | semver-file | dated}
**Window:** [N] commits since [baselineRef] ([baselineReason])

**Files updated:**

- `{changelog path}` — added [N] entries
- `{product path}` — updated [sections]
- `{version file}` — version bumped (omit under semver-tag / dated)

**Next steps:**

1. Review the changes in each file
2. Commit: `git add -A && git commit -m "chore(release): prepare vA.B.C"`
3. Tag: `git tag vA.B.C` (semver schemes only)
4. Push: `git push && git push --tags`
```

---

## Examples

See `examples/` directory for full walkthroughs:

- `examples/minor-release.md` — Feature release with new capabilities
- `examples/patch-release.md` — Bug-fix-only release

## References

- `references/CONFIG.md` — the `release_prep` config section and what each key overrides
- `references/EDGE-CASES.md` — unreachable tags, dated projects, bootstrap runs, missing files
- `references/PRODUCT-TEMPLATE.md` — PRODUCT.md skeleton for a first run

---

## Rules

- **Append-only:** Never rewrite existing changelog or PRODUCT.md sections
- **Follow the file:** Match the existing document's convention; never migrate it to a new style
- **Respect the scheme:** Never bump a version under `dated`; never edit a manifest under `semver-tag`
- **User-facing only:** Internal commits never appear in "What's New"
- **Confirm bumps:** Always ask the user before bumping major versions
- **Preserve history:** Re-read files after editing to verify no data loss

---

## Success Criteria

- [ ] Baseline was reviewed — unreachable tags and `no-baseline` windows raised with the user
- [ ] All commits in the window are analyzed
- [ ] The changelog entry matches the existing file's convention and heading style
- [ ] Changelog preserves ALL previous entries (re-read to verify)
- [ ] PRODUCT.md contains no internal/technical changes (tests, refactors, SDK upgrades)
- [ ] PRODUCT.md core feature sections updated for any new user-facing capabilities
- [ ] PRODUCT.md preserves ALL previous "What's New" sections (re-read to verify)
- [ ] Version handled per `versionScheme` — bumped, tagged, or deliberately untouched
- [ ] Summary provided with next steps

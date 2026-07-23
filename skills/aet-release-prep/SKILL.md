---
name: aet-release-prep
description: Automate release preparation by analyzing commits since the last tag, detecting the project's versioning scheme, suggesting semantic version bumps, and updating CHANGELOG.md and PRODUCT.md. Use when preparing a release, updating changelogs, bumping versions, or keeping product documentation current. Triggers on "prepare release," "update changelog," "release prep," "version bump," or "what's new in this release."
---

# aet-release-prep

Automate release preparation by analyzing git commits since the last tag and generating documentation updates.

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

## Step 1: Analyze Commits Since Last Tag

Run the release-prep subcommand to get all commits since the last git tag:

```bash
aet release-prep
```

The command outputs JSON with:

- `lastTag` — The most recent git tag
- `currentVersion` — Version from detected source (package.json, VERSION file, or latest tag)
- `versionSource` — Which source was used (`package.json`, `VERSION`, or `git-tag`)
- `commits` — Array of commits with hash, subject, body, and type classification
- `suggestedBump` — Recommended version bump (`major` / `minor` / `patch`)
- `nextVersion` — Calculated next version

**Confirm with the user:**

- Does the suggested version bump look correct?
- Are there any commits that should be classified differently?

---

## Step 2: Update CHANGELOG.md

Update `CHANGELOG.md` at the repository root with the new release.

### CRITICAL: Append-Only Rule

**NEVER replace or modify existing version sections.** CHANGELOG.md is an append-only document.

1. **Read the entire file first** to understand the existing structure
2. **Insert the new version section** between the file header and the first existing `## [x.y.z]` entry
3. **Do NOT touch any existing version sections** — they are historical records
4. If a version section already exists for the target version, UPDATE only that section (do not duplicate)

### Format

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

### Guidelines

1. **Group commits by type** (Added, Changed, Fixed, Documentation)
2. **Write user-facing descriptions** — translate technical commits into benefits
3. **Include PR/issue references** if mentioned in commit body
4. **Skip internal commits** (CI, build tooling) unless significant
5. **Combine related commits** into single entries when they address the same feature
6. **Verify after editing** — read the file again to confirm all previous versions are still present

---

## Step 3: Update PRODUCT.md

Update `PRODUCT.md` at the repository root with current product capabilities.

PRODUCT.md is a **product snapshot** for cross-functional teams (Marketing, Sales, Support). It documents features at a user level — not implementation details. Every line should read as **product documentation**, never as a developer changelog.

### CRITICAL: Preserve Existing "What's New" Sections

PRODUCT.md contains a **"What's New in vX.Y.Z"** section for each release. These are **historical records** — treat them the same as CHANGELOG entries.

1. **Read the entire file first** to understand the existing structure
2. **Do NOT delete or modify** any previous "What's New in vX.Y.Z" sections
3. **Verify after editing** — read the file again to confirm all previous "What's New" sections are still present

### Step 3a: Triage Commits — User-Facing vs Internal

Before writing anything, categorize **every commit** from the release into one of two buckets:

| Category        | What belongs here                                                                                                             | Examples                                                                                       |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **USER-FACING** | New features users can see/click, UX changes, new integrations, new shipped skills, bug fixes users were hitting              | "Add Project Assistant skill", "Add chat starter suggestions", "Fix permission queue blocking" |
| **INTERNAL**    | Tests, SDK upgrades, refactors, naming conventions, build/CI, logging, migration internals, dead code removal, dev-only fixes | "Add 173 E2E tests", "Upgrade Agent SDK", "Rename skill prefixes", "Extract shared helper"     |

**Rule of thumb:** If a user wouldn't notice the change while using the app, it's INTERNAL.

### Step 3b: Update Core Feature Sections (Primary Output)

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

### Step 3c: Update "What's New" Section (Brief Marketing Summary)

Insert a new "What's New in vX.Y.Z" section at the TOP of the "What's New" area (before existing ones).

**Rules:**

- **Only user-facing changes** from the Step 3a triage — zero internal items
- **3–8 bullets max** — combine related changes, cut ruthlessly
- **Write benefit statements**, not technical descriptions
- **No "plus technical improvements" catch-all** — if it's not user-facing, it doesn't belong

**Good vs bad bullets:**

| ✅ Good (benefit statement)                                     | ❌ Bad (developer changelog)                  |
| --------------------------------------------------------------- | --------------------------------------------- |
| Project Assistant skill for AI-guided project setup             | Added SessionStart hook for context injection |
| Chat starter suggestions to help you begin conversations faster | 173 E2E tests across 6 test suites            |

### Step 3d: Verify

1. **Read the file again** after editing to confirm:
   - All previous "What's New" sections are still present
   - Header version and date are updated
   - Core feature sections are updated for new capabilities
2. **Consumer-focus check:** Read every line you added and ask: _"Does this read as product documentation, or as a developer changelog?"_ If the latter, rewrite or remove it
3. Use the Edit tool for targeted changes — never rewrite the entire file

---

## Step 4: Bump Version

Update version in the detected source:

1. **Read current version** from script output (includes `versionSource`)
2. **Confirm suggested bump** with user (major/minor/patch)
3. **Edit the appropriate file:**
   - Git tags only — for this project the version is derived from the git tag, so there is no file to edit. Note the next version for the user to tag manually

---

## Step 5: Summary

After completing all updates, provide a summary:

```markdown
## Release Prep Complete

**Version bump:** X.Y.Z → A.B.C (patch/minor/major)
**Version source:** {package.json | VERSION | git-tag}

**Files updated:**

- `CHANGELOG.md` — Added [N] entries
- `PRODUCT.md` — Updated [sections]
- `{package.json | VERSION}` — Version bumped

**Commits analyzed:** [N] commits since [last-tag]

**Next steps:**

1. Review the changes in each file
2. Commit: `git add -A && git commit -m "chore(release): prepare vA.B.C"`
3. Tag: `git tag vA.B.C`
4. Push: `git push && git push --tags`
```

---

## Examples

See `examples/` directory for full walkthroughs:

- `examples/minor-release.md` — Feature release with new capabilities
- `examples/patch-release.md` — Bug-fix-only release

## Edge Cases

See `references/edge-cases.md` for handling:

- No tags exist
- No commits since last tag
- Missing CHANGELOG.md or PRODUCT.md
- Only internal commits (no user-facing changes)

---

## Rules

- **Append-only:** Never rewrite existing CHANGELOG or PRODUCT.md sections
- **User-facing only:** Internal commits never appear in "What's New"
- **Confirm bumps:** Always ask the user before bumping major versions
- **Preserve history:** Re-read files after editing to verify no data loss

---

## Success Criteria

- [ ] All commits since last tag are analyzed
- [ ] Version bump follows semantic versioning correctly
- [ ] CHANGELOG.md has user-friendly descriptions grouped by type
- [ ] CHANGELOG.md preserves ALL previous version sections (re-read to verify)
- [ ] PRODUCT.md contains no internal/technical changes (tests, refactors, SDK upgrades)
- [ ] PRODUCT.md core feature sections updated for any new user-facing capabilities
- [ ] PRODUCT.md preserves ALL previous "What's New" sections (re-read to verify)
- [ ] Version source updated (package.json, VERSION, or noted for git tags)
- [ ] Summary provided with next steps

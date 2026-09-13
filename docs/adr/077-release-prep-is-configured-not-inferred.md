---
subject: release-prep-resolution
relates: []
---

# Release Prep Is Configured, Not Inferred

## Status

Accepted.

## Context

`aet release-prep` resolved every input to a release by inference: the version
came from the first manifest it found, the release window came from
`git describe`, and the documents it updated were assumed to be `CHANGELOG.md`
and `PRODUCT.md` at the repository root. Each inference is right often enough to
look correct and wrong quietly enough to go unnoticed.

Running the command across four real repositories surfaced four distinct
failures, none of which reported an error:

1. **A polyglot repo bumps the wrong manifest.** A Python project whose version
   is derived from git tags by `setuptools-scm` also carried a frontend
   `package.json`. Detection returned `package.json` and its unrelated `1.0.0`,
   so the suggested bump named a file no release ever reads.

2. **Unreachable tags widen the window to everything.** A repository seeded from
   a vendored upstream import carried that project's tags, none of them
   ancestors of HEAD. `git describe` fails outright on this shape. The failure
   was read as "no tags exist", so the release window silently became the entire
   history — 195 commits instead of 30 — while the output simultaneously listed
   five tags.

3. **A continuously deployed project is handed a version number.** A fleet
   repository states in its own changelog that it has no version numbers and
   dates its entries instead. The command proposed a semantic bump anyway,
   sourced from a vestigial `version = "0.1.0"` that nothing consumes.

4. **Document locations are assumed.** Two projects keep these documents under
   `content/` and `docs/`. A run against them would have created a second,
   empty changelog at the root beside the real one.

The common shape: an ambiguous input resolved silently to a plausible-looking
wrong answer. The fix is not better heuristics — it is making each resolution
declarable, reporting how it was reached, and refusing to guess where guessing
is unsafe.

## Decision

**Every release input is declarable in `.agents/aet-config.json`, auto-detected
when absent, and reported with the reason it resolved the way it did.**

The `release_prep` section accepts `changelog_path`, `product_path`,
`version_scheme`, `version_file`, and `baseline_ref`. Each key is optional; a
present key wins outright, an absent key is detected. This follows the two-layer
config precedent of ADR-048 and the section-per-lens convention already used by
`boundary_contract` and `symlink_dependencies`.

Three consequences of that decision are load-bearing:

**Ancestry is checked, not assumed.** Baseline resolution uses
`git tag --merged HEAD` rather than `git describe`, so a tag that is not an
ancestor can never become a baseline. Such tags are reported separately in
`unreachableTags` rather than discarded, because their presence is exactly the
signal that a human should confirm the window. The fallback chain is explicit:
`--since`, config, newest reachable tag, last commit that touched the changelog,
then nothing.

**`dated` is a first-class version scheme.** A project that deploys
continuously has no version to bump, and the absence of one is a deliberate
choice rather than a missing manifest. Under `dated`, `suggestedBump` and
`nextVersion` are `null` and no manifest is touched. The scheme is inferred from
the changelog's own shape — dated headings with no version headings — so a
project that has already made the choice needs no config to have it respected.

**Existing layout is preserved over convention.** Document paths probe for an
existing file before falling back to a default, so an established `content/` or
`docs/` layout is never relocated by a release run.

Failures that were previously silent now fail loudly: an unresolvable
`baseline_ref` or `--since` is an error rather than a fallback to the whole
history, and an unrecognized `version_scheme` is rejected rather than defaulted.

## Consequences

- The command remains usable with zero configuration; detection covers the
  common cases and the config exists for the exact ones.
- The output carries `baselineReason`, `versionSchemeReason`, and document
  `origin` fields, so the skill can explain and challenge a resolution rather
  than acting on it blindly.
- `bootstrap` is reported explicitly, separating "seed these documents" from
  "append one entry" — two jobs the command previously conflated.
- Version detection now reads `pyproject.toml` and `composer.json` in addition
  to `package.json` and `VERSION`, and recognizes `setuptools-scm` ahead of all
  of them.
- Repositories wanting exact behavior must add a config section; nothing forces
  them to, and no existing repository's behavior changes without one.

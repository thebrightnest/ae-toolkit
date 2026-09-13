# Release Prep Configuration

`aet release-prep` auto-detects everything it needs and works in an unconfigured
checkout. The `release_prep` section of `.agents/aet-config.json` exists to make
a resolution **exact** where detection would be ambiguous or wrong.

Every key is optional. A key that is absent is auto-detected; a key that is
present wins outright.

```json
{
  "release_prep": {
    "changelog_path": "CHANGELOG.md",
    "product_path": "docs/PRODUCT.md",
    "version_scheme": "semver-tag",
    "version_file": "pyproject.toml",
    "baseline_ref": "v1.0.0"
  }
}
```

## Keys

### `changelog_path` / `product_path`

Where each document lives, relative to the repo root.

Detection probes, in order, and the first file that exists wins:

- changelog — `CHANGELOG.md`, `docs/CHANGELOG.md`, `content/CHANGELOG.md`
- product — `docs/PRODUCT.md`, `PRODUCT.md`, `content/PRODUCT.md`

An established layout is therefore never relocated by a release run. When
nothing exists yet, the defaults are `CHANGELOG.md` and `docs/PRODUCT.md` —
where a first run will create them.

Set these when the document lives somewhere the probe does not look, or when you
want to **move** it: a configured path that does not exist yet is reported with
`exists: false`, and the skill creates it there.

### `version_scheme`

One of:

| Value | Meaning |
| --- | --- |
| `semver-tag` | The git tag is the version. Nothing in the tree to edit. |
| `semver-file` | A manifest holds the version string and gets bumped. |
| `dated` | No version numbers at all. Entries are dated; nothing is ever bumped. |

Detection, in order:

1. A changelog whose newest heading is a date and which has **no** version
   headings is `dated`. A continuously deployed project is recognized from its
   own changelog, with no config needed.
2. A `setuptools-scm`, `git-tag`, or absent version source is `semver-tag`.
3. An editable manifest is `semver-file`.

Set this when the changelog is too new to carry the signal, or when the project
is converting from one scheme to another. An unrecognized value is an error, not
a fallback.

### `version_file`

The manifest holding the version string, relative to the repo root. Parsed by
name and extension: `pyproject.toml` (`[project].version`, then
`[tool.poetry].version`), any `.json` (`version` key), anything else as a plain
first line.

Detection, in order: `setuptools-scm` (a `[project] dynamic = ["version"]`
declaration alongside a `[tool.setuptools_scm]` table), `package.json`,
`VERSION`, `pyproject.toml`, `composer.json`, latest git tag, then `0.0.0`.

Set this in a polyglot repo where detection picks the wrong manifest — for
example a Python project carrying a frontend `package.json` whose version is
unrelated to the release.

### `baseline_ref`

The git ref the release window starts from.

Detection, in order:

1. `--since` on the command line
2. `baseline_ref` from this config
3. The newest tag **reachable from HEAD** (`git tag --merged HEAD`)
4. The last commit that touched the changelog
5. Nothing — the whole history, reported as `baselineReason: no-baseline`

Ancestry is checked deliberately. `git describe` fails outright on a repo whose
tags sit on an abandoned or vendored line of history, and treating that failure
as "no tags" silently widens the window to everything ever committed. Such tags
are reported separately in `unreachableTags` so the skill can raise them instead
of ignoring them.

Set this after a bootstrap run, so the next run is incremental. A ref that does
not resolve is an error, not a fallback — a typo must not silently widen the
window.

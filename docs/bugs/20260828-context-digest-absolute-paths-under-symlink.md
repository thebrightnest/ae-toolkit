# Bug Report: the context digest emits absolute paths when the repo root is reached through a symlink

## Metadata

- **Reported:** 2026-08-28
- **Severity:** low (token cost and leaked local paths; no wrong decision)
- **Status:** fixed 2026-08-28

## Symptoms

`aet context --hook-json <harness>` emits an absolute path where a repo-relative
one is specified:

```
"last_plan": "/var/folders/x1/…/T/tmp8ef3/docs/plans/feat-002.md"
```

against a golden envelope that reads:

```
"last_plan": "docs/plans/feat-002.md"
```

`tests/cli/test_context.py::TestContextCommand::test_context_hook_json_matches_golden_fixture`
fails on every macOS run for this reason, and had been failing on `main` before
2026-08-28 — verified at `568b1807`, the commit that preceded that day's work.

## Reproduction Steps

```python
tmp = Path(tempfile.mkdtemp())            # /var/folders/…/T/tmpX     (macOS)
subprocess.run(["git", "init", "-q", str(tmp)])
subprocess.run(["git", "-C", str(tmp), "rev-parse", "--show-toplevel"])
# -> /private/var/folders/…/T/tmpX
(tmp / "docs" / "x.md").relative_to(Path(top))
# ValueError: '/var/…/docs/x.md' is not in the subpath of '/private/var/…'
```

## Root Cause

`_git_root` (`cli/context.py:65-73`) returns git's own answer to
`rev-parse --show-toplevel`, which has symlinks resolved. Collected paths are
built from the working directory as given, which does not. `_repo_relative`
compared the two spellings directly and failed open:

```python
try:
    return str(path.relative_to(repo_root))
except ValueError:
    return str(path)
```

On macOS `/var` is a symlink to `/private/var`, so every temp-dir repo hits this;
in the field, any repository reached through a symlink does — a home directory on
another volume, a checkout under a symlinked work root.

The failure is invisible on Linux, where `/tmp` is not a symlink, which is why
the golden fixture was written and reviewed as correct.

## Why It Survived The Gate

`make validate` runs the impact-scoped target set from `aet.change_scope`, and
`tests/cli/test_context.py` was not in it for any change made earlier in the
session. It entered the set only when `AGENTS.md` and `docs/CONVENTIONS.md`
changed, which widened the scope to the full suite and surfaced a red that had
been sitting on `main`.

That is the more interesting half of this report: an impact-scoped gate reports
green over a pre-existing failure until an unrelated change happens to select it.
Filed as `content/backlog/debt-impact-scope-can-hide-a-standing-red.md`.

## Fix

`_repo_relative` resolves both sides before comparing, and catches `OSError`
alongside `ValueError` so an unreadable path still degrades to the absolute
spelling rather than raising. The golden fixtures are unchanged: they always
described the correct output.

## Consequences

The digest is what a session reads at startup, so an absolute path was paid for
in tokens on every hook invocation under a symlinked root, and leaked a local
filesystem layout into whatever consumed the envelope. Neither changed a
decision, which is why it went unnoticed for as long as the fixture did.

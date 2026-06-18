# Bug Report: `make package` is non-deterministic (`.skill` artifacts churn every run)

## Metadata

- **Reported:** 2026-06-18T16:53:21Z
- **Severity:** medium
- **Status:** fixed

## Symptoms

`make package` rewrites the committed `.skill` archives with **byte-different but
content-identical** output on every run. On a clean tree, a single `make package`
leaves **all 21** `.skill` files modified — each with an identical byte size and
**0** line changes. Every PR that regenerates packages therefore carries spurious
binary churn for all skills, which defeats the `aet-ship` scope-audit/diff signal
and makes the committed artifacts impossible to review by diff.

(The `fods-01` PR shipped exactly this noise: ~20 `.skill` files shown as
`Bin N -> N bytes`.)

## Reproduction Steps

1. Start from a clean working tree (`git status --short -- '*.skill'` empty).
2. `make package`
3. `git status --short -- '*.skill'` → **all 21** `.skill` files modified.
   `git diff --stat -- '*.skill'` → every entry `Bin N -> N bytes`,
   `0 insertions(+), 0 deletions(-)`.
4. `git checkout -- '*.skill'` to restore.

## Root Cause

`Makefile:37`:

```make
zip -r "$$skill.skill" "$$skill" -x "*.git*" -x "*node_modules*" -x "*.DS_Store" -x "*__pycache__*" -x "*.pyc";
```

The ZIP format stores each entry's **modification timestamp** (DOS date/time in the
local + central-directory headers), and `zip` reads it from the filesystem. File
mtimes are not stable across git operations (checkout, merge, worktree add, clone),
so re-zipping identical content produces different archive bytes. There is no mtime
normalization, no `-X`, and `zip` updates the archive in place.

- **Wrong assumption:** zipping identical content yields identical bytes.
- **Note:** no `SKILL.md.template` files exist in the repo, so the `build-skills.py`
  assembly branch in the `package` target never runs — the nondeterminism is purely
  the `zip` step, not template regeneration.
- **Why not caught:** `.skill` artifacts are committed but never byte-compared;
  `make validate` checks structure, not reproducibility.

## Fix Summary (applied)

- **Files modified:**
  - `Makefile`: normalize entry mtimes to a fixed epoch before zipping and strip
    extra metadata with `zip -X`.
  - `scripts/check-reproducible-package.sh`: new regression test that packages
    twice and compares SHA-256 checksums.
  - `docs/plans/2026-06-18-fix-nondeterministic-skill-packaging.md`: plan
    documenting the change.
- **Key change:** `find "$$skill" -exec touch -t 198001010000 {} +` followed by
  `zip -X -r "$$skill.skill" "$$skill" ...`. This fixes DOS date/time fields and
  removes UID/GID/extra filesystem metadata from the archive.
- **Regression test:** `make check-reproducible` now runs the packaging step twice
  and fails if any `.skill` archive bytes differ.
- **Quality gate:** `make validate` now includes `make check-reproducible`, so
  non-deterministic packaging will be caught locally before shipping.
- **Risk:** low.

## Regression Test

Added `scripts/check-reproducible-package.sh`. It runs `make package` twice,
computes SHA-256 checksums of all `*.skill` files after each pass, and fails if
the checksums differ. Invoked via `make check-reproducible` and included in
`make validate`.

## Validation

- [x] Reproduction steps no longer trigger the bug
- [x] Existing test suite passes with no new failures
- [x] No regressions observed in related functionality

## Lessons Learned

- **Pattern:** build artifacts committed to VCS that are not byte-reproducible.
- **Prevention:** make packaging deterministic (fixed timestamps) or don't commit
  generated artifacts; add a "package is reproducible" check.
- **Reference:** surfaced during `fods-01` ship verification.

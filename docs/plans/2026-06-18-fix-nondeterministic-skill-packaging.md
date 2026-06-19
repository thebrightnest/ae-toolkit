---
id: 2026-06-18-fix-nondeterministic-skill-packaging
blocked_by: []
size: S
---

# Plan: Fix Non-Deterministic Skill Packaging

## Problem

`make package` rewrites all `.skill` archives with byte-different but content-identical output on every run because `zip` stores filesystem mtimes, which are unstable across git operations.

## Root Cause

`Makefile:37` calls `zip -r` without mtime normalization (`-X`) or fixed timestamps.

## Fix

1. **Normalize skill directory mtimes** to a fixed epoch before zipping.
2. **Use `zip -X`** to strip UID/GID and extra filesystem metadata.
3. **Add a reproducibility regression test** that runs `make package` twice and asserts `.skill` byte checksums are identical.
4. **Wire the test into `make validate`** so future packaging regressions are caught.

## Files to Modify

| File                                                           | Change                                                                                   |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `Makefile`                                                     | Normalize mtimes; use `zip -X`; add `check-reproducible` target; call it from `validate` |
| `scripts/check-reproducible-package.sh`                        | New script: package twice, compare SHA-256 checksums                                     |
| `docs/bugs/2026-06-18-skill-packaging-nondeterministic-zip.md` | Update status to `fixed` and validation checklist                                        |

## Validation

- [ ] `make check-reproducible` passes
- [ ] `make validate` passes
- [ ] No `.skill` churn across consecutive `make package` runs

## Size

S — 2 files, ≤ 50 diff lines.

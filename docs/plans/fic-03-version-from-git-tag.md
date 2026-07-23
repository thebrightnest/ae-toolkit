---
id: fic-03-version-from-git-tag
size: S
blocked_by: []
pipeline: standard
status: queued
security_review: skipped
security_review_reason: build-backend configuration and version derivation; no auth, data, network, or filesystem trust boundary is touched
docs_sync: required
docs_sync_reason: releases become git tag only and the pyproject version field disappears; the release runbook and aet-release-prep guidance must stop instructing a manual bump
---

# Plan: Derive the version from the git tag

## Context

- PRD: `docs/prds/fresh-install-correctness-prd.md` (R-26, R-27)
- ADR: `docs/adr/043-version-derives-from-the-git-tag.md`
- Bug: `docs/bugs/2026-07-22-fresh-install-v140-installer-and-path-link-failures.md`
  (defect 3)

`pyproject.toml:7` reads `version = "1.3.0"` while `v1.4.0` was tagged from it:

```
$ git show v1.4.0:pyproject.toml | grep '^version'
version = "1.3.0"
```

Every v1.4.0 install reports `aet 1.3.0`. The 2026-07-22 reporter could not
state which version they were running — the first question any maintainer asks.

The build backend is already `hatchling` (`pyproject.toml:1-3`), so `hatch-vcs`
is a configuration change rather than a migration.

**The divergence is already live in the tooling.** `detect_version_source()`
(`src/aet/cli/release_prep.py:55-85`) resolves `package.json` → `VERSION` →
git tag → `0.0.0`. It never reads `pyproject.toml`. This repo has no
`package.json` and no `VERSION`, so `aet release-prep` already reports the
**tag** while the shipped artifact reports **pyproject** — two sources of truth
with no reconciliation between them. This plan makes the tag the only one, which
is the source `release_prep` already uses.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

The stale number is a defect (tracked in the bug report). Removing the
possibility of drift is the enhancement, and is the substance of this plan.

## Locked design

- **Reverses the owner decision of 2026-07-22** to add a release-time
  tag/version consistency gate. That option was chosen from three that all left
  two sources of truth; deriving the version removes the class instead of
  detecting it. Recorded in ADR-043.
- `hatch-vcs` added to `[build-system].requires`; `[project].version` replaced
  by `dynamic = ["version"]` with the `hatch-vcs` source configured. The static
  string is **deleted**, not updated to `1.4.0`.
- `aet --version` code is unchanged — it already reads
  `importlib.metadata.version("aet")` (`main.py:178-180`).
- **No release gate is added.** If the version cannot disagree with the tag,
  there is nothing to gate.
- Between tags the version carries a dev suffix
  (e.g. `1.4.0.dev3+g5b2db1a`). This is intended: bug reports from unreleased
  checkouts become self-identifying.

## Task List

1. ✓ In `pyproject.toml`: add `hatch-vcs` to `[build-system].requires`, replace
   `[project].version` with `dynamic = ["version"]`, delete the static
   `version = "1.3.0"` string (`:7`), and configure the `hatch-vcs` version
   source — S (traces: R-26)
2. ✓ Verify `aet --version` matches `git describe` in an editable install, at a
   tag, and between tags — S (traces: R-26)
3. ✓ Verify an sdist built without `.git` present still yields a correct version
   via the `hatch-vcs` fallback — S (traces: R-27)
4. ✓ Update `skills/aet-release-prep/SKILL.md:194-201` — "Update version in the
   detected source" keeps only its `git-tag` branch for this project: cutting a
   release is `git tag`, there is no file to edit — S (traces: R-26)
5. ✓ Leave `src/aet/cli/release_prep.py` unchanged and record why in the PR: it
   already resolves to the git tag for this repo, so nothing there needs to
   learn about `pyproject.toml` — S (traces: R-26)
6. [Deferred: merge to main and verify integration is the next stage (`aet-ship`)]

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated against the full guardrail model.

### Batching Check

- [x] Not one of several near-identical additions
- [ ] The diff is expected to exceed 3 files or 50 lines — it does not (~30
      lines), but the docs sync and the release-process change make it a
      distinct concern from the installer work
- [x] Cannot share a branch with `fic-01`/`fic-02` — different subsystem (build
      and release configuration vs. CLI and installer)

## Rejected Alternatives

Full treatment in ADR-043. Recorded so they are not re-opened:

- **A release gate that fails on tag/version mismatch** — rejected, and
  initially chosen. It detects drift rather than preventing it, keeps two
  sources of truth, and adds a check to maintain in order to police a step that
  stays manual.
- **Have `aet release-prep` write the bump** — rejected: turns a reporting
  command into a mutating one, and still leaves the tag as a separate step that
  can disagree.
- **Just fix the number to `1.4.0`** — rejected: recurs at v1.5.0.
- **`setuptools-scm`** — equivalent, rejected only because the backend is
  `hatchling`.

## Files to Modify

- `pyproject.toml`
- `skills/aet-release-prep/SKILL.md`

Deliberately **not** modified: `src/aet/cli/release_prep.py` (task 5). There is
no separate release runbook — `docs/releases/` holds per-release notes, not
process, and `AGENTS.md:12` mentions `pyproject.toml` only for dev
dependencies.

## Validation Steps

- [x] Lint passes
- [x] Tests pass
- [x] No new source files introduced; no new test module required — the
      assertion that `aet --version` matches `pyproject`/tag is added to the
      installer suite by `fic-04` (R-30) rather than duplicated here
- [x] Test type: integration — build and install in a temp venv, compare
      `aet --version` against `git describe --tags`
- [ ] `aet --version` at a tagged commit reports the tag without a dev suffix
      (can only be verified at a tag; standard hatch-vcs behavior)
- [x] `aet --version` between tags reports a dev suffix identifying the commit
- [x] `python -m build --sdist` in a tree without `.git` yields a correct
      version (traces: R-27)
- [x] `grep -n '^version' pyproject.toml` returns nothing (traces: R-26)
- [ ] `scripts/install.sh` still produces a correctly-versioned install — it
      uses a full `git clone` then `checkout <tag>`, so tags are present. If a
      future change adds `--depth 1`, this breaks silently; noted in ADR-043
      (deferred to `aet-ship`/live verification)
- [x] R-trace coverage: R-26 (1, 2, 4), R-27 (3)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`
      (deferred to `aet-ship`)

## Rollback Plan

Revert the commit; the static version field returns. Any release cut while this
was active keeps its correct tag-derived version, so rollback does not
retroactively corrupt published artifacts. Restore the field to the last tag's
value, not to `1.3.0`.

## Pipeline

`standard`.

⚠️ VALIDATE ACK: rtrace — R-8 and R-9 cited in the PRD Requirements section belong to `uv-one-line-installer-prd.md` (inline supersession context in R-16/R-18), not to this PRD; the R-id sweep counts any mention.

---

*Stage: synced*
*Next step: run `aet-ship`*

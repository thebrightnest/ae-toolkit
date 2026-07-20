---
id: pkg-06-cross-skill-extraction
size: M
blocked_by:
  - pkg-04-cli-extraction
pipeline: standard
status: queued
security_review: required
security_review_reason: Task 5 is no longer a pure relocation once amended; it adds a new CLI subcommand surface and a full bash-to-Python behavior port, which is behavior-review relevant even without a new dependency.
docs_sync: required
docs_sync_reason: SKILL.md Prerequisites sections and CONVENTIONS.md references to per-skill bin/ dirs must be updated in the same change.
---

# Plan: Extract Cross-Skill Binaries into the Package (A1e)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-2, R-3,
R-11) and `docs/prds/namespace-consolidation-prd.md` (R-4). The dispatcher's
`SUBCOMMANDS` currently reaches into three other skill directories:
`aet-ship/bin/ship`, `aet-evolve/bin/{aet-retro,mine-learnings}`,
`aet-setup/bin/{configure-task-backend,harness-guard,hooks}`, plus
`aet-setup/lib/harness_guard.py`. Move all of them into `src/aet/cli/` /
`src/aet/`, completing the rule "no Python inside skill directories" and
enabling the old dispatcher file to be deleted. Task 5 now also traces R-4:
`aet-release-prep/release-prep.sh` is promoted into the package as
`aet release-prep` rather than relocated, satisfying R-4's acceptance criterion
that no executable script remains at the skill root.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. [x] Move `aet-ship/bin/ship` → `src/aet/cli/ship.py`,
   `aet-evolve/bin/{aet-retro,mine-learnings}` → `src/aet/cli/`,
   `aet-setup/bin/{configure-task-backend,harness-guard,hooks}` →
   `src/aet/cli/`, each with `main()`; move `aet-setup/lib/harness_guard.py` →
   `src/aet/harness_guard.py` — M (traces: R-2)
2. [x] Move `aet-work/bin/aet` (dispatcher) → `src/aet/cli/main.py` with
   `SUBCOMMANDS` targets fully inside the package; delete `aet-work/bin/` and
   the other skills' `bin/`/`lib/` dirs — M (traces: R-2)
3. [x] Update `Makefile` (`install-skills` invokes the installed `aet` entry point,
   not `./aet-work/bin/aet`) — S (traces: R-3)
4. [x] Update SKILL.md Prerequisites in `aet-ship`, `aet-evolve`, `aet-setup`,
   `aet-work` to reference the installed `aet` entry point (no repo-relative
   bin paths); update `docs/CONVENTIONS.md` canonical-installer paragraph — S
   (traces: R-11)
5. [x] Port `aet-release-prep/release-prep.sh`'s logic (version-source detection
   across `package.json`/`VERSION`/git-tag with `v`-prefix stripping, commit
   classification including conventional-commit prefixes and keyword fallbacks,
   semver bump calculation including prerelease-stripping, JSON output) with
   equivalent behavior to a new `aet release-prep` Python subcommand at
   `src/aet/cli/release_prep.py`; delete `aet-release-prep/release-prep.sh`
   entirely — no relocation, since R-4's acceptance criterion requires no
   executable script remaining at the skill root; update the invocation
   reference in `aet-release-prep/SKILL.md` Step 1 from the script path to
   `aet release-prep` — M (traces: R-2, R-4, R-11)
6. [x] Update affected tests (`test_aet_ship.py`, `test_aet_retro.py`,
   `test_hooks_install.py`, `test_aet_setup_backend_config.py`,
   `test_aet_setup_examples.py`, dispatcher tests) — M (traces: R-3)
7. [Deferred: pending ship/merge stage] Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] One cohesive sweep completing the "no code in skills" rule; kept
      separate from pkg-04 because the source-of-truth review domain differs
      (aet-work vs. the satellite skills).

## Rejected Alternatives

- **Leave the dispatcher at `aet-work/bin/aet`** — rejected: it would be the
  last Python file inside a skill, defeating the phase goal and the pkg-08
  validator rule.
- **Keep per-skill `bin/` as thin shims** — rejected: shims re-introduce the
  fragmentation this phase removes; the dispatcher already provides the
  single entry point.

## Files to Modify

- `aet-ship/bin/ship` → `src/aet/cli/ship.py`
- `aet-evolve/bin/{aet-retro,mine-learnings}` → `src/aet/cli/`
- `aet-setup/bin/{configure-task-backend,harness-guard,hooks}` → `src/aet/cli/`
- `aet-setup/lib/harness_guard.py` → `src/aet/harness_guard.py`
- `aet-work/bin/aet` → `src/aet/cli/main.py`
- `aet-release-prep/release-prep.sh` (deleted)
- `src/aet/cli/release_prep.py` (new)
- `Makefile`
- `aet-ship/SKILL.md`, `aet-evolve/SKILL.md`, `aet-setup/SKILL.md`,
  `aet-work/SKILL.md` (Prerequisites sections),
  `aet-release-prep/SKILL.md` (script path reference)
- `docs/CONVENTIONS.md` (Skill Binaries / canonical installer)
- Affected `tests/test_aet_*.py`, `tests/test_hooks_install.py`,
  `tests/test_aet_setup_*.py`

## Validation Steps

- [ ] `find aet-work aet-ship aet-evolve aet-setup aet-release-prep -name "*.py" -o -name "*.sh" -o -type d -name bin -o -type d -name lib`
      returns nothing
- [ ] `tests/test_aet_ship.py`, `tests/test_aet_retro.py`,
      `tests/test_hooks_install.py`, `tests/test_aet_multicall.py` (named,
      existing) pass against package locations
- [ ] `make install-skills` completes using the installed `aet install`
- [ ] All dispatcher subcommands (`aet ship`, `aet retro`,
      `aet mine-learnings`, `aet hooks`, `aet harness-guard`,
      `aet configure-backend`) behave identically
- [ ] `tests/test_release_prep.py` passes, covering version-source detection
      across all three sources, commit classification including keyword fallbacks,
      and bump calculation including prerelease-stripping
- [ ] `aet-release-prep/release-prep.sh` no longer exists post-merge
- [ ] `make validate` green
- [ ] R-trace coverage: R-2 by tasks 1–2, 5; R-3 by tasks 3, 6; R-4 by task 5;
      R-11 by tasks 4–5; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge; per-skill bin dirs and the old dispatcher return
together. PATH symlinks created by `aet install` still resolve because the
revert restores the targets they point at.

---

*Stage: synced*
*Next step: run `aet-ship`*

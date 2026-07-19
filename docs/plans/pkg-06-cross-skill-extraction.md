---
id: pkg-06-cross-skill-extraction
size: M
blocked_by:
  - pkg-04-cli-extraction
pipeline: standard
status: approved
security_review: skipped
security_review_reason: Pure relocation of ship/retro/setup binaries into the package; no behavior or dependency changes.
docs_sync: required
docs_sync_reason: SKILL.md Prerequisites sections and CONVENTIONS.md references to per-skill bin/ dirs must be updated in the same change.
---

# Plan: Extract Cross-Skill Binaries into the Package (A1e)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-2, R-3,
R-11). The dispatcher's `SUBCOMMANDS` currently reaches into three other skill
directories: `aet-ship/bin/ship`, `aet-evolve/bin/{aet-retro,mine-learnings}`,
`aet-setup/bin/{configure-task-backend,harness-guard,hooks}`, plus
`aet-setup/lib/harness_guard.py`. Move all of them into `src/aet/cli/` /
`src/aet/`, completing the rule "no Python inside skill directories" and
enabling the old dispatcher file to be deleted.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Move `aet-ship/bin/ship` → `src/aet/cli/ship.py`,
   `aet-evolve/bin/{aet-retro,mine-learnings}` → `src/aet/cli/`,
   `aet-setup/bin/{configure-task-backend,harness-guard,hooks}` →
   `src/aet/cli/`, each with `main()`; move `aet-setup/lib/harness_guard.py` →
   `src/aet/harness_guard.py` — M (traces: R-2)
2. Move `aet-work/bin/aet` (dispatcher) → `src/aet/cli/main.py` with
   `SUBCOMMANDS` targets fully inside the package; delete `aet-work/bin/` and
   the other skills' `bin/`/`lib/` dirs — M (traces: R-2)
3. Update `Makefile` (`install-skills` invokes the installed `aet` entry point,
   not `./aet-work/bin/aet`) — S (traces: R-3)
4. Update SKILL.md Prerequisites in `aet-ship`, `aet-evolve`, `aet-setup`,
   `aet-work` to reference the installed `aet` entry point (no repo-relative
   bin paths); update `docs/CONVENTIONS.md` canonical-installer paragraph — S
   (traces: R-11)
5. Move `aet-release-prep/release-prep.sh` → `scripts/release-prep.sh` (bash
   helper, not a Python subcommand — repo tooling, not package code); update
   the invocation reference in `aet-release-prep/SKILL.md` — S (traces: R-2,
   R-11)
6. Update affected tests (`test_aet_ship.py`, `test_aet_retro.py`,
   `test_hooks_install.py`, `test_aet_setup_backend_config.py`,
   `test_aet_setup_examples.py`, dispatcher tests) — M (traces: R-3)
7. Merge branch to main and verify integration — S

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
- `aet-release-prep/release-prep.sh` → `scripts/release-prep.sh`
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
- [ ] `make validate` green
- [ ] R-trace coverage: R-2 by tasks 1–2, 5; R-3 by tasks 3, 6; R-11 by tasks
  4–5; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge; per-skill bin dirs and the old dispatcher return
together. PATH symlinks created by `aet install` still resolve because the
revert restores the targets they point at.

---

*Stage: plan-approved*
*Next step: run `aet-work`*

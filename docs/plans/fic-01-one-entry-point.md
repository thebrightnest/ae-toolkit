---
id: fic-01-one-entry-point
size: M
blocked_by: []
pipeline: standard
status: approved
security_review: required
security_review_reason: deletes and retargets symlink creation in the user bin directory and removes an os.execv at module scope; path-resolution correctness is security-relevant, inherited from cli-04
docs_sync: required
docs_sync_reason: reverses a locked cli-04 decision, supersedes R-8 of the uv installer PRD, renames aet install to aet setup link, and drops a supported invocation mode
---

# Plan: Make the console script the only entry point

## Context

- PRD: `docs/prds/fresh-install-correctness-prd.md` (R-15…R-19, R-33 — the doc
  sweep for the `aet install` → `aet setup link` rename: `README.md`,
  `docs/CONVENTIONS.md`, release notes)
- ADR: `docs/adr/041-console-script-is-the-only-entry-point.md`
- Bug: `docs/bugs/2026-07-22-fresh-install-v140-installer-and-path-link-failures.md`
  (defect 2)
- Reverses: `docs/plans/cli-04-aet-install-self-repair.md` (merged 2026-07-11)

Three mechanisms currently answer "how does `aet` get on PATH under a working
interpreter." This plan deletes two of them. Rationale and rejected alternatives
are in ADR-041 and are not re-opened at implementation time.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

Routed here *from* `aet-bug-report` under its structural-redesign rule. The
defect is reproduced and root-caused in the bug report; this plan is the
structural replacement, which is not itself a defect fix.

## Locked design

- Delete `_ensure_path_link()`, `_running_script()`, and the callback call site
  (`main.py:196-197`). The callback retains only the `--version` option wiring.
- Delete the direct-script invocation mode: the `#!/usr/bin/env python3` shebang
  (`main.py:1`), the `if __name__ == "__main__"` block (`main.py:479-480`), and
  the module-level bootstrap guard including `_can_import_aet()` and the
  `os.execv` re-exec (`main.py:12-49`).
- `aet install` becomes `aet setup link`, in `src/aet/cli/setup.py` alongside
  `setup skills`. Its target is `Path(sys.executable).parent / "aet"` when that
  exists, falling back to `Path(__file__).resolve()` only for source-checkout
  invocation.
- **No alias, no deprecation window.** The repo's convention is clean cuts; `aet
  install` is removed, not shimmed.
- Retain `_is_worktree_copy()` and `_link_target_resolves_to()`, moved with the
  command. R-9 requires the worktree refusal; `setup link` needs the resolver to
  report "already linked" vs "updated stale symlink".
- `_bin_dir()` and its `AET_BIN_DIR` override are retained — the test suite
  isolates through it and `install.sh` passes `--bin-dir`.

## Task List

1. Delete `_ensure_path_link()`, `_running_script()`, and the callback call
   site — S (traces: R-15)
2. Delete the shebang, `__main__` block, and module-level bootstrap guard;
   verify `python -m aet.cli.main` and the console script both still work — S
   (traces: R-17)
3. Move `install` to `aet setup link` in `src/aet/cli/setup.py`, retargeted at
   the console script; move `_is_worktree_copy`, `_link_target_resolves_to`,
   `_bin_dir` with it; remove `install` from `main.py` and its callback
   exemption — M (traces: R-16, R-18)
4. Correct the module docstring (`main.py:2-8`), which asserts
   `_ensure_path_link` remains for single-name PATH ownership — S (traces: R-19)
5. Rewrite `tests/cli/test_aet_install.py` as `tests/setup/test_setup_link.py`:
   delete `TestSelfRepair` (`:138-228`) and the self-repair half of
   `TestWorktreeCopyGuard` (`:239-250`); retarget the `aet install` coverage at
   `aet setup link`; add `test_subcommand_does_not_touch_link` — M
   (traces: R-15, R-16, R-18)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated against the full guardrail model.

### Guardrail check

- Subsystems: `src/aet/` (code + its tests) — one coherent subsystem.
- Expected diff: ~250 lines, majority deletion (bootstrap guard ~38 lines,
  self-repair ~45, `TestSelfRepair` ~90).
- Context budget: `main.py` (481 lines) + `setup.py` + `test_aet_install.py`
  (315 lines) — under 30k tokens.

### Batching Check

- [x] Not one of several near-identical additions
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with `fic-02` — different subsystem (shell installer
      vs. CLI), and this one carries the security review

## Rejected Alternatives

Full treatment in ADR-041. Recorded so they are not re-opened:

- **Fix `_running_script()` and keep self-repair** — rejected: preserves
  "invoked copy wins," so a second `aet` still hijacks the link by running, and
  the bootstrap guard must stay to compensate.
- **Narrow self-repair to dangling links only** — rejected: third consecutive
  narrowing of a mechanism with two corruption incidents behind it.
- **Keep the bootstrap guard as defense in depth** — rejected: it cannot succeed
  on a packaged install, works in a checkout only by layout coincidence, and its
  only beneficiary is the invocation mode being removed.
- **Keep `aet install` as an alias for `aet setup link`** — rejected: the repo
  takes clean cuts over deprecation windows.
- **Delete `_is_worktree_copy()` as incidental cleanup** — rejected: still
  required by R-9 for `setup link`.

## Files to Modify

- `src/aet/cli/main.py`
- `src/aet/cli/setup.py`
- `tests/cli/test_aet_install.py` → `tests/setup/test_setup_link.py`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] No new source files introduced. Coverage for the relocated command lands
      in `tests/setup/test_setup_link.py` with named cases:
      `test_fresh_link_targets_console_script`,
      `test_stale_link_repaired`,
      `test_non_symlink_collision_skipped`,
      `test_path_warning_prints_export_line`,
      `test_refuses_worktree_copy`,
      `test_subcommand_does_not_touch_link` — seed `<bin-dir>/aet` at a distinct
      file, run a real subcommand (`aet status`), assert `readlink` unchanged
- [ ] Test types: unit tests over link-target resolution; integration test
      invoking a real subcommand through the seeded link
- [ ] `test_subcommand_does_not_touch_link` demonstrated **failing** against
      current `main.py` before the change (traces: R-32)
- [ ] Manual check on a packaged install: `aet setup link` from a non-editable
      venv produces a link that executes. R-16's failure mode is invisible to an
      editable-install suite — this is the check that would have caught the
      shipped defect
- [ ] `python -m aet.cli.main plans lint` and `python -m aet.cli.main docs lint`
      still work (`Makefile:100-101` depends on both)
- [ ] `scripts/skills-lint` still imports `from aet.cli.main import app`
- [ ] `grep -rn "_ensure_path_link\|_running_script" src/ tests/` returns nothing
- [ ] `grep -rn "aet install" skills/ docs/ README.md` — every hit updated to
      `aet setup link`
- [ ] `aet-cso` invoked — symlink creation in the user bin directory
- [ ] R-trace coverage: R-15 (1, 5), R-16 (3, 5), R-17 (2), R-18 (3, 5), R-19 (4)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit; `cli-04`'s behavior returns. Reverting reinstates a
known-broken behavior on packaged installs, so rollback is appropriate only if
`aet setup link` proves worse — not as a response to an unrelated regression.

Users holding a corrupted link (pointing at `site-packages/aet/cli/main.py`) are
repaired by re-running `install.sh` or `aet setup link`. Release notes must
state that the link is no longer self-healing and that `aet install` is gone.

## Pipeline

`standard`. Symlink and PATH-ownership changes warrant the default stage
grouping with a real security review rather than `minimal`.

---

*Stage: plan-approved*
*Next step: run `aet-work`*

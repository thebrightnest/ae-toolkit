---
id: fic-01-one-entry-point
size: M
blocked_by: []
pipeline: standard
status: queued
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
6. Update `README.md` (`:144`, `:169`) and `docs/CONVENTIONS.md` (`:57-59`) to
   name `aet setup link`; add the release-notes line naming re-running the
   installer as the repair for v1.4.0-corrupted links — S (traces: R-33)
   — **release-notes half deferred to release-prep**: `CHANGELOG` edits are
   blocked on feature branches by `scripts/prevent-release-on-feature-branch.sh`.
   Wording to carry over is in the Rollback Plan below.
7. Merge branch to main and verify integration — S

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
- `README.md`
- `docs/CONVENTIONS.md`

## Validation Steps

- [x] Lint passes — `ruff check .` clean (`make lint-py`)
- [x] Tests pass — `make validate` green: 1026 passed + 5 installer tests
- [x] No new source files introduced. Coverage for the relocated command lands
      in `tests/setup/test_setup_link.py` with named cases:
      `test_fresh_link_targets_console_script`,
      `test_stale_link_repaired`,
      `test_non_symlink_collision_skipped`,
      `test_path_warning_prints_export_line`,
      `test_refuses_worktree_copy`,
      `test_subcommand_does_not_touch_link` — seed `<bin-dir>/aet` at a distinct
      file, run a real subcommand (`aet status`), assert `readlink` unchanged
- [x] Test types: unit tests over link-target resolution; integration test
      invoking a real subcommand through the seeded link
- [x] `test_subcommand_does_not_touch_link` demonstrated **failing** against
      current `main.py` before the change (traces: R-32). First draft was a
      false green — it passed against pre-change `main.py` because the suite
      runs from `.worktrees/`, where the old `_ensure_path_link()` bailed at its
      own worktree guard before touching the link. Guard now neutralised in the
      test; verified failing pre-change, passing post-change. The subprocess
      integration test had the same hole *and* skipped itself post-change; it
      now stages the package outside `.worktrees` and always runs
- [x] Manual check on a packaged install: `aet setup link` from a non-editable
      venv produces a link that executes. R-16's failure mode is invisible to an
      editable-install suite — this is the check that would have caught the
      shipped defect. Verified: package resolved to
      `site-packages/aet/cli/main.py`, link produced was `<venv>/bin/aet` (the
      console script, not `__file__`), and `<bin>/aet --version` printed
      `aet 1.3.0`
- [x] `python -m aet.cli.main plans lint` and `python -m aet.cli.main docs lint`
      still work (`Makefile:100-101` depends on both) — see deviation note below
- [x] `scripts/skills-lint` still imports `from aet.cli.main import app`
- [x] `grep -rn "_ensure_path_link\|_running_script" src/ tests/` returns nothing
- [x] `grep -rn "aet install" skills/ docs/ README.md` — every hit updated to
      `aet setup link`. Remaining tree-wide hits are historical records (merged
      plans, superseded PRDs/ADRs, the v1.0.0 release note) and are deliberately
      left intact; the PRD's own acceptance criterion scopes this to
      `README.md` + `docs/CONVENTIONS.md`, both clean
- [ ] `aet-cso` invoked — symlink creation in the user bin directory
- [x] R-trace coverage: R-15 (1, 5), R-16 (3, 5), R-17 (2), R-18 (3, 5), R-19 (4),
      R-33 (6)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

### Deviation from locked design (task 2)

ADR-041 decision 2 lists the `if __name__ == "__main__"` block for deletion
while naming `python -m aet.cli.main` a supported invocation. Those are
contradictory: that block *is* what `-m` dispatches through. Deleting it left
the module importable but inert — `python -m aet.cli.main plans lint` exited 0
with no output, silently disabling the `make validate` gate at `Makefile:100-101`
and breaking 9 tests across the suite.

Resolved by keeping the `__main__` block and deleting only the direct-script
machinery the ADR actually targets: the shebang and the module-level bootstrap
guard. Without a shebang or re-exec, an interpreter that cannot import `aet` now
fails loudly at import instead of silently re-execing — which is the ADR's
stated intent. Guarded by
`test_module_invocation_propagates_subcommand_exit_code` and
`test_console_script_dispatches`; ADR-041 needs a correction to decision 2.

## Rollback Plan

Revert the commit; `cli-04`'s behavior returns. Reverting reinstates a
known-broken behavior on packaged installs, so rollback is appropriate only if
`aet setup link` proves worse — not as a response to an unrelated regression.

Users holding a corrupted link (pointing at `site-packages/aet/cli/main.py`) are
repaired by re-running `install.sh` or `aet setup link`. Release notes must
state that the link is no longer self-healing and that `aet install` is gone.

**Carry into the next release's `CHANGELOG`** (blocked on this branch by the
release-guard hook): if `~/.local/bin/aet` points at
`site-packages/aet/cli/main.py` (the v1.4.0 self-repair defect), re-run
`scripts/install.sh` or `aet setup link` to repoint it at the console script.
`aet install` is removed and the symlink is no longer self-healing.

## Pipeline

`standard`. Symlink and PATH-ownership changes warrant the default stage
grouping with a real security review rather than `minimal`.

⚠️ VALIDATE ACK: rtrace — R-8 and R-9 cited in the PRD Requirements section belong to `uv-one-line-installer-prd.md` (inline supersession context in R-16/R-18), not to this PRD; the R-id sweep counts any mention.

---

*Stage: secure*
*Next step: run `aet-sync-docs`, then `aet-ship`*

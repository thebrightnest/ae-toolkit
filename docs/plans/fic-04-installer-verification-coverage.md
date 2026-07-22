---
id: fic-04-installer-verification-coverage
size: M
blocked_by:
  - fic-01-one-entry-point
  - fic-02-installer-bootstrap-boundary
  - fic-03-version-from-git-tag
pipeline: standard
status: queued
security_review: skipped
security_review_reason: test-only plan; adds coverage over the install path without changing any shipped code or trust boundary
docs_sync: skipped
docs_sync_reason: no user-facing behavior changes; the coverage rules it establishes belong in the test file, not in user documentation
---

# Plan: Close the gap that let three defects ship

## Context

- PRD: `docs/prds/fresh-install-correctness-prd.md` (R-28…R-32)
- ADR: `docs/adr/042-the-installer-is-a-bootstrap.md`
- Bug: `docs/bugs/2026-07-22-fresh-install-v140-installer-and-path-link-failures.md`
  (defect 4)

`tests/installer/test_installer.py` passed on every commit that shipped the
three defects. That is the defect this plan addresses — the suite tested a
configuration no user runs:

| Line | What it does | Why the defect was invisible |
|---|---|---|
| `:92-95`, `:122-128`, `:166-171` | every invocation passes `--agent generic` or `--skills-dir`, and sets `AET_SKILLS_DIR` | `skills_args` is never empty, so the bash-3.2 crash cannot occur |
| `:135` | `aet_bin = aet_link.resolve()` before running | the callback never sees the symlink, so it cannot corrupt it |
| `:140-157` | only `--help` and `--version` are executed | both are eager Typer options that exit **before** the callback body |
| `:157` | `assert "aet" in version_result.stdout` | passes for `aet 1.3.0` at tag v1.4.0 |
| `:33` | `[str(INSTALLER), ...]` — invoked via shebang | runs whatever `bash` the shebang finds, not necessarily `/bin/bash` 3.2 |

Four independent choices, each individually reasonable, that together made the
suite blind to the exact failure a real user hit on the first try.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

The missing coverage is recorded as defect 4 in the bug report. Establishing the
coverage rules that make the class detectable is the enhancement.

## Locked design

- **The default configuration is the primary test case.** The existing
  flag-heavy tests are kept — they cover explicit-flag behavior — but the
  no-flag path becomes the one the smoke test exercises first.
- "No flags" means: **no** `--agent`, **no** `--skills-dir`, **no** `--bin-dir`,
  and `AET_SKILLS_DIR` **unset**. `--repo`, `--tag`, and an isolated `HOME` are
  retained for hermeticity — the suite must not clone over the network or write
  to the developer's real `~/.local`. `AET_DATA_DIR`/`AET_BIN_DIR` derive from
  the isolated `HOME` rather than being passed, so the default derivation
  (`install.sh:8-10`) is itself covered.
- **Tests execute the unresolved link.** `subprocess.run([str(bin_dir / "aet"),
  "status"])` — not `.resolve()`, and not `--help`/`--version`. `os.readlink` is
  compared before and after.
- **The subcommand must reach the callback body.** `--help` and `--version` are
  eager Typer options and exit first, which is why the current suite could not
  observe the corruption.
- Version is asserted **exactly** against `git describe --tags`, not by
  substring.
- The installer is invoked as `["/bin/bash", str(INSTALLER), ...]`, so the bash
  under test is the one macOS ships.
- **Every test here is written and demonstrated failing first**, against the
  pre-`fic-01`/`fic-02`/`fic-03` code, with output pasted into the PR. A test
  never seen red is how this suite reached its current state.
- `fic-01` adds `test_subcommand_does_not_touch_link` as a **unit** test over
  `setup link`. This plan adds the **integration** counterpart through a real
  installer run. Both are intended: the unit test is fast feedback, the
  integration test is the one that would have caught the shipped defect.

## Task List

1. Add `test_installs_with_no_flags`: isolated `HOME`, `AET_SKILLS_DIR` unset,
   no `--agent`/`--skills-dir`/`--bin-dir`; assert exit 0 and a working link —
   M (traces: R-28)
2. Add `test_subcommand_through_link_does_not_rewrite_it`: capture
   `os.readlink(bin_dir / "aet")`, run a real subcommand through the
   **unresolved** link, re-read, assert equal — M (traces: R-29)
3. Replace the `"aet" in stdout` assertion (`:157`) with an exact match against
   `git describe --tags`; depends on `fic-03` — S (traces: R-30)
4. Change `run_installer` (`:32-37`) to invoke `["/bin/bash", str(INSTALLER),
   ...]`; assert `/bin/bash` exists so a runner without it fails loudly rather
   than skipping silently — S (traces: R-31)
5. Add a module docstring to `tests/installer/test_installer.py` recording the
   four coverage rules (no-flag default, unresolved link, real subcommand, exact
   version) so the next author does not re-introduce the gap — S
   (traces: R-28, R-29, R-30)
6. Demonstrate each new test failing against pre-fix code; record the output in
   the PR description — S (traces: R-32)
7. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated against the full guardrail model.

### Guardrail check

- Subsystems: `tests/` only — one subsystem, no source changes.
- Expected diff: ~150 lines added to a 174-line file.
- Context budget: `test_installer.py` (174 lines) + `install.sh` (257 lines) —
  well under 30k tokens.

### Batching Check

- [x] Not one of several near-identical additions — each test targets a distinct
      blind spot
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with `fic-01`/`fic-02`/`fic-03` — it asserts the end
      state all three produce

## Blocking rationale

Blocked by all three. Task 3 asserts a tag-derived version (`fic-03`); tasks 1
and 4 assert the no-flag path survives (`fic-02`); task 2 asserts the link
survives a subcommand (`fic-01`). Landing earlier would add three failing tests
to `main`.

This ordering has a real cost: it is the reverse of test-first. Task 6 buys the
discipline back — each test is authored against pre-fix code and seen red on a
scratch branch before this plan's branch lands it green. The alternative,
splitting each test into the plan that fixes its defect, would scatter one
coherent coverage change across three branches and leave no single place stating
why the suite was blind.

## Rejected Alternatives

- **Fold each test into the plan that fixes its defect** — rejected per the
  blocking rationale above. Kept only where the test is genuinely unit-scope
  (`fic-01`'s `test_subcommand_does_not_touch_link`).
- **Add a CI runner instead** — rejected here; worth doing separately. R-13 of
  the uv installer PRD already accepted local-only gates, and CI would not have
  caught these defects because the tests themselves were passing.
- **Test on a bash 3.2 container** — rejected: macOS developers already have 3.2
  at `/bin/bash`; pinning the interpreter costs one line and no infrastructure.
- **Keep `.resolve()` and assert on the resolved target** — rejected: that is
  precisely the choice that hid the defect.

## Files to Modify

- `tests/installer/test_installer.py`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] No new source files introduced — this plan is test-only. New test cases,
      each named: `test_installs_with_no_flags`,
      `test_subcommand_through_link_does_not_rewrite_it`,
      `test_version_matches_git_describe`,
      `test_installer_runs_under_bin_bash`
- [ ] Test types: integration (full installer run against a local repo
      checkout). No unit tests are appropriate here — the gap being closed is
      specifically the absence of end-to-end coverage
- [ ] Each new test demonstrated **failing** against pre-fix code, output pasted
      into the PR (traces: R-32)
- [ ] `grep -n 'resolve()' tests/installer/test_installer.py` — no remaining use
      that resolves the link before executing it (traces: R-29)
- [ ] `grep -n '"aet" in' tests/installer/test_installer.py` returns nothing
      (traces: R-30)
- [ ] Suite runtime does not regress materially — an added full install run is
      the most expensive test in the repo; if it pushes the installer suite past
      ~60s, mark it `slow` rather than dropping it
- [ ] R-trace coverage: R-28 (1, 5), R-29 (2, 5), R-30 (3, 5), R-31 (4),
      R-32 (6)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. No shipped behavior changes, so rollback is safe — but it
restores the blindness that produced this PRD, and should be paired with a
recorded reason.

## Pipeline

`standard`.

⚠️ VALIDATE ACK: rtrace — R-8 and R-9 cited in the PRD Requirements section belong to `uv-one-line-installer-prd.md` (inline supersession context in R-16/R-18), not to this PRD; the R-id sweep counts any mention.

---

*Stage: plan-approved*
*Next step: run `aet-work`*

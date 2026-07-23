---
id: fic-02-installer-bootstrap-boundary
size: M
blocked_by:
  - fic-01-one-entry-point
pipeline: standard
status: queued
security_review: required
security_review_reason: rewrites the curl-piped-to-bash install path and moves symlink creation across the shell/Python boundary; this is the highest-trust code the project ships
docs_sync: required
docs_sync_reason: adds aet setup verify as a user-facing diagnostic and changes installer output; README Quick Start and troubleshooting must describe both
---

# Plan: Reduce `install.sh` to a bootstrap

## Context

- PRD: `docs/prds/fresh-install-correctness-prd.md` (R-20…R-25)
- ADR: `docs/adr/042-the-installer-is-a-bootstrap.md`
- Bug: `docs/bugs/2026-07-22-fresh-install-v140-installer-and-path-link-failures.md`
  (defects 1 and 5)

`install.sh` is 257 lines of bash that must survive macOS bash 3.2. Only the
first stages need to be shell; everything after `uv pip install` runs on a
known-good interpreter with `aet` importable. The empty-array crash exists
because bash marshals arguments for `aet setup skills` — a Typer program that
already parses flags.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

The crash is a defect (tracked in the bug report). Relocating the shell/Python
boundary so the defect class cannot recur is the enhancement, and is the
substance of this plan.

## Locked design

- **The bash boundary is `uv pip install`.** Shell keeps: `ensure_uv`,
  `resolve_tag`, `clone_or_update_repo`, `create_venv_and_install`, and the
  `--help`/error plumbing needed before Python exists.
- **The array is removed, not guarded.** Shell forwards `"$@"` to the installed
  CLI. Flag parsing, agent validation, and defaults move to Typer. Do not add
  `${skills_args[@]+"${skills_args[@]}"}` — that is the patch this plan exists
  to avoid. The one exception is `scripts/validate-skills.sh` (task 6), which is
  off the installer path and gets the guard rather than a rewrite.
- Shell still parses the minimum needed *before* the clone exists: `--repo`,
  `--tag`, `--dry-run`, `--help`. Everything else is forwarded untouched.
- **Unknown flags still fail fast, in bash, before the clone.** Forwarding
  `"$@"` blindly would defer rejection to Typer — after `uv` is bootstrapped, the
  repo cloned, and the venv built, which is a worse failure than today's. The
  shell therefore keeps a *recognition* list (`--agent`, `--bin-dir`,
  `--skills-dir`) separate from a *parsing* list: recognized flags and their
  values are appended to `"$@"` untouched and never inspected; anything else is
  an error before any work happens. This preserves
  `test_unknown_flag_exits_nonzero` (`test_installer.py:62-65`).
- **`install.sh --help` keeps documenting every flag** (`install.sh:24-32`),
  including the forwarded ones. `TestInstallerHelp` (`:46-56`) asserts on
  `--agent`, `--bin-dir`, and `--skills-dir` and must keep passing; the shell
  documents what it accepts even where Typer is what validates the value.
- Validation of flag *values* — a bad `--agent` name — moves to Typer (task 5)
  and is therefore reported after the venv exists. That is the accepted cost:
  a misspelled agent is rarer than a misspelled flag, and Typer's message is
  better than the bash `case` it replaces.
- **`aet setup verify` is read-only.** It resolves what `aet` runs on `PATH`
  (equivalent of `command -v aet`), compares against the expected link, and
  reports. It never edits `PATH`, shell profiles, or other installations, and
  exits 0 when the install succeeded but is shadowed — that install did succeed.
- `--dry-run` is honored on both sides of the boundary; the Python side must
  print planned actions and touch nothing.
- Depends on `aet setup link` from `fic-01`.

## Task List

1. Add `aet setup verify` to `src/aet/cli/setup.py`: resolve the `PATH`-winning
   `aet`, compare to the expected link, report shadowing by name; read-only,
   exit 0. Cover it with a new `tests/setup/test_setup_verify.py` — M
   (traces: R-23)
2. Strip `install_skills()` and `link_aet_binary()` from `install.sh`; replace
   with a single hand-off invoking `setup skills`, `setup link`, and
   `setup verify` on the installed CLI — M (traces: R-20, R-22)
3. Reduce shell flag parsing to `--repo`, `--tag`, `--dry-run`, `--help`;
   recognize-and-forward `--agent`, `--bin-dir`, `--skills-dir` via `"$@"` while
   still erroring on anything unrecognized before the clone; delete the
   `skills_args` array and the `AGENT` validation `case` — M (traces: R-21)
4. Thread `--dry-run` across the boundary so the Python side prints planned
   actions and modifies nothing — S (traces: R-24)
5. Move agent validation (`claude-code|kimi|cursor|generic`) into the Typer
   layer so the error message comes from one place — S (traces: R-21)
6. Guard the three `SKILL_DIRS` expansions in `scripts/validate-skills.sh`
   (`:26`, `:103`, `:141`) — S (traces: R-25)
7. Update README Quick Start and troubleshooting for `aet setup verify` and the
   shadowing warning — S (traces: R-23)
8. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated against the full guardrail model.

### Guardrail check

- Subsystems: `scripts/` (installer shell) + `src/aet/` (setup command and its
  tests), with a README paragraph. At the two-subsystem boundary; acceptable
  because the change *is* the boundary between them.
- Expected diff: ~200 lines — roughly 130 removed from bash, ~70 added in
  Python.
- Context budget: `install.sh` (257 lines) + `setup.py` + README section —
  under 30k tokens.

### Batching Check

- [x] Not one of several near-identical additions
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with `fic-01` — different subsystem, and this plan
      consumes `aet setup link` as a dependency

## Blocking rationale

Blocked by `fic-01` because task 2 invokes `aet setup link`, which `fic-01`
creates. Landing this first would leave the installer calling a command that
does not exist.

## Rejected Alternatives

Full treatment in ADR-042. Recorded so they are not re-opened:

- **Add the `${skills_args[@]+"${skills_args[@]}"}` guard and stop** — rejected
  as the durable fix, though it is the correct emergency patch if a release is
  needed before this lands. It fixes two lines and leaves ~90 lines of
  hand-rolled bash arg parsing plus the rest of the bash-3.2 footgun surface in
  the least-tested code path the project ships.
- **Rewrite the installer in POSIX `sh`** — rejected: removes arrays by removing
  the feature rather than the need, and still leaves install logic in a language
  with no test story here.
- **Require bash 4+ via the shebang** — rejected: macOS ships 3.2 permanently,
  and the documented invocation pipes into `bash`, so the shebang is never
  consulted.
- **Move the bootstrap into Python** (`pipx`/`uvx` one-liner) — rejected for
  now: trades a controlled shell bootstrap for assuming the user already has a
  specific Python tool, which is the problem the installer solves.
- **Have the installer fix PATH shadowing** — rejected: `cli-04` already
  rejected editing shell profiles as "the wrong kind of magic"; removing another
  installation is outside an installer's remit.
- **Fail the install on shadowing** — rejected: the install genuinely succeeded,
  and failing would break legitimate multi-install setups.

## Files to Modify

- `scripts/install.sh`
- `scripts/validate-skills.sh`
- `src/aet/cli/setup.py`
- `tests/setup/test_setup_verify.py` (new)
- `README.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] **New source file** — `tests/setup/test_setup_verify.py` covers
      `aet setup verify` (`src/aet/cli/setup.py`) with named cases:
      `test_reports_ok_when_link_wins_path`,
      `test_reports_shadowing_path_by_name`,
      `test_exits_zero_when_shadowed`,
      `test_reports_dangling_link`,
      `test_never_mutates_path_or_link`
- [ ] Test types: unit tests over `PATH` resolution with a synthetic `PATH`;
      integration test through the real installer in `fic-04`
- [ ] `bash -n scripts/install.sh && bash -n scripts/validate-skills.sh`
- [ ] `grep -n 'skills_args' scripts/install.sh` returns nothing (traces: R-21)
- [ ] `/bin/bash scripts/install.sh --dry-run` with no other flags exits 0
- [ ] Installer remains idempotent: second run exits 0 and changes nothing
      (R-10 of the uv installer PRD still holds)
- [ ] `aet-cso` invoked — this is the curl-piped-to-bash path
- [ ] R-trace coverage: R-20 (2), R-21 (3, 5), R-22 (2), R-23 (1, 7), R-24 (4),
      R-25 (6)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The installer returns to its current form, including the
bash-3.2 crash — so rollback must be paired with the emergency array guard if it
happens after a release. Note this explicitly in the PR description.

No state or artifact is migrated; already-installed users are unaffected by a
revert of the installer.

## Pipeline

`standard`. The curl-piped-to-bash path is the project's highest-trust surface
and warrants the full review grouping.

⚠️ VALIDATE ACK: rtrace — R-8 and R-9 cited in the PRD Requirements section belong to `uv-one-line-installer-prd.md` (inline supersession context in R-16/R-18), not to this PRD; the R-id sweep counts any mention.

---

*Stage: reviewed*
*Next step: run `aet-cso`*

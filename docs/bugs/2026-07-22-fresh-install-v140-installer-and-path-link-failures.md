# Bug Report: fresh macOS install of v1.4.0 fails at the installer, then corrupts its own `aet` symlink

## Metadata

- **Reported:** 2026-07-22T00:00Z
- **Severity:** critical (the documented one-line install cannot succeed on stock macOS; when worked around, the resulting install breaks itself on first use)
- **Status:** open — all five routed to `aet-plan`. The owner rejected in-place
  patching on 2026-07-22; see Fix Summary.

## Symptoms

Reported from a clean macOS 26.5.1 (arm64) machine installing v1.4.0 via the
documented one-liner. Two independent user-visible failures, plus three defects
found while confirming them.

**A. The installer aborts partway through.**

```
curl -fsSL https://raw.githubusercontent.com/thebrightnest/ae-toolkit/main/scripts/install.sh | bash
```

```
  linking skills
install.sh: line 198: skills_args[@]: unbound variable
```

Exit status 1 *after* cloning the repo, creating the venv, and installing the
package, but *before* linking skills and creating `~/.local/bin/aet` — the user
is left with a partial install and no `aet` on PATH. In the piped form the error
scrolls past and the two skipped steps are easy to miss.

**B. Once installed, the CLI breaks itself on first real use.**

```
$ aet --version
Traceback (most recent call last):
  File "/Users/<user>/.local/bin/aet", line 58, in <module>
    from aet.cli import (  # noqa: E402
ModuleNotFoundError: No module named 'aet'
```

Install → works; run one real subcommand → broken. Repairing the symlink by hand
lasts exactly until the next `aet` invocation.

## Reproduction Steps

**Defect 1 — empty-array expansion under `set -u` (verified on this machine):**

```
$ /bin/bash --version | head -1
GNU bash, version 3.2.57(1)-release (x86_64-apple-darwin24)

$ /bin/bash -c 'set -euo pipefail; a=(); echo "${a[@]}"; echo ok'
/bin/bash: a[@]: unbound variable      # rc=1

$ /bin/bash -c 'set -euo pipefail; a=(); echo "${a[*]}"; echo ok'
/bin/bash: a[*]: unbound variable      # rc=1  ← the --dry-run branch

$ /bin/bash -c 'set -euo pipefail; a=(); echo "fixed:" ${a[@]+"${a[@]}"}; echo ok'
fixed:
ok
```

Triggered by the documented one-liner with **no options**: neither
`AET_SKILLS_DIR` nor `AGENT` is set, so `skills_args` stays empty.

**Defect 2 — symlink rewritten to a module path (verified on this machine):**

```
$ AET_BIN_DIR=$TMP/bin .venv/bin/python -c "
import os, pathlib, importlib
aet = importlib.import_module('aet.cli.main')
link = pathlib.Path(os.environ['AET_BIN_DIR'])/'aet'
link.symlink_to(pathlib.Path(os.environ['AET_BIN_DIR'])/'venv-aet')
print('before:', os.readlink(link)); aet._ensure_path_link(); print('after :', os.readlink(link))"

_running_script() -> /Users/<user>/Sites/aiskills/src/aet/cli/main.py
before: .../bin/venv-aet
after : /Users/<user>/Sites/aiskills/src/aet/cli/main.py
```

Original reporter's end-to-end form:

```bash
curl -fsSL .../install.sh | bash -s -- --agent claude-code   # link -> venv/bin/aet (correct)
readlink ~/.local/bin/aet    # .../venv/bin/aet
aet status >/dev/null        # any real subcommand
readlink ~/.local/bin/aet    # .../site-packages/aet/cli/main.py  ← rewritten
aet --version                # ModuleNotFoundError: No module named 'aet'
```

`aet --version` alone does not trigger it — the eager version option exits
before the callback body runs.

**Defect 3 — version drift:**

```
$ git show v1.4.0:pyproject.toml | grep '^version'
version = "1.3.0"
```

## Root Cause

Five distinct defects. Only the first two were user-reported; 3–5 were found
while confirming them.

### Defect 1 — `install.sh` expands empty arrays under `set -u` (bash ≤ 4.3)

`scripts/install.sh` runs under `set -euo pipefail`. In `install_skills()`,
`skills_args` is populated only when `AET_SKILLS_DIR` or `AGENT` is set, so the
default one-liner leaves it empty. bash treats expanding an empty array as an
unbound-variable error until 4.4; macOS ships bash 3.2 permanently.

- `scripts/install.sh:198` — `"${skills_args[@]}"` (the reported crash)
- `scripts/install.sh:193` — `${skills_args[*]}` in the `--dry-run` branch
  **(not in the original report)**; `--dry-run` without `--agent` fails
  identically

**Why tests did not catch it:** see defect 4 — every installer test passes
`--agent` or `--skills-dir`, so the array is never empty in CI.

Latent, same pattern: `scripts/validate-skills.sh:26,103,141` expand
`"${SKILL_DIRS[@]}"` under `set -euo pipefail`. Safe only because `skills/` is
never empty — it is one empty directory away from the same crash.

### Defect 2 — `_ensure_path_link()` links to a module, not the entry script (structural)

`src/aet/cli/main.py:127`:

```python
def _running_script() -> Path:
    """Return the resolved path of this running copy."""
    return Path(__file__).resolve()
```

Under a packaged install `__file__` is
`…/venv/lib/python3.14/site-packages/aet/cli/main.py` — the module, not the
console script. `_ensure_path_link()` (`main.py:151`), called from the app
callback on every non-`install` subcommand (`main.py:196`), sees the
installer-created link does not resolve to that path, unlinks it, and repoints
`~/.local/bin/aet` at `main.py`. That file's shebang is `#!/usr/bin/env python3`,
so the command then runs under **system** Python, which has no `aet` package →
`ModuleNotFoundError`.

The bootstrap guard at `main.py:35-49` is what normally hides this in
development: it re-execs into a discovered venv. From site-packages its
candidate roots are `venv/lib/python3.14` (checking
`venv/lib/python3.14/.venv/bin/python` and `…/bin/python`, neither of which
exists) and `Path.cwd()` — so on a packaged install the guard finds nothing,
falls through to the import at line 58, and raises. It only appears to work
where the default `python3` happens to have `aet` installed, i.e. a dev machine.

**What assumption was wrong.** This is a stale premise, not a typo.
`docs/plans/cli-04-aet-install-self-repair.md` locked "the invoked copy wins"
self-repair on 2026-07-11, when `aet` was a **source-checkout script** at
`aet-work/bin/aet`. In that world `__file__` *was* the entry point and
`_is_worktree_copy()` was the necessary guard. The uv installer (uvi-02, shipped
in v1.4.0) changed deployment to a packaged console script in a venv, which
invalidated the premise without updating the code that depended on it.

cli-04's stated justification — "a rarely-run manual step whose omission
surfaces later as `command not found`" — no longer holds either: `install.sh`
now creates and repoints the link in `link_aet_binary()`, and re-running the
installer is the documented update path.

**Compounding harm.** Because self-repair fires from *whichever* copy runs, an
unrelated `aet` install clobbers the link to its own site-packages. Observed
live: an older pyenv-installed `aet` shadowed `~/.local/bin` on PATH, so every
invocation both ran the wrong copy and corrupted the correct link.

This one requires redesign, not a patch → routed to `aet-plan` per the
`aet-bug-report` structural-redesign rule. **Owner decision (2026-07-22):**
delete on-invocation self-repair entirely; the installer owns the link. Manual
linking survives as `aet setup link`, retargeted at the console script — see
ADR-041 and `fic-01`.

### Defect 3 — `pyproject.toml` version not bumped at release

`pyproject.toml:7` reads `version = "1.3.0"` while `v1.4.0` was tagged from it,
so `aet --version` misreports on every v1.4.0 install and complicates
diagnosing which version a user actually has. `aet release-prep` computes
`nextVersion` (`src/aet/cli/release_prep.py:216`) but nothing writes it back —
no code in `src/aet/` mutates the pyproject version. The bump is a manual step
with no guardrail, so it will drift again.

### Defect 4 — the installer smoke tests structurally cannot catch defects 1–3

`tests/installer/test_installer.py`:

- Every test passes `--agent generic` or `--skills-dir`
  (`:92-95`, `:122-128`, `:166-171`), so `skills_args` is **never empty** — the
  documented no-options one-liner has no coverage at all.
- The smoke test resolves the link (`aet_bin = aet_link.resolve()`, `:135`) and
  runs only `aet --help` and `aet --version` against it. Both exit before the
  callback body, so `_ensure_path_link()` never fires and defect 2 is invisible.
  No test executes a real subcommand *through* `~/.local/bin/aet`.
- `assert "aet" in version_result.stdout` (`:157`) passes for `aet 1.3.0` — this
  is precisely how defect 3 shipped.
- The script is invoked as `[str(INSTALLER), …]` (`:33`), i.e. via the
  `#!/usr/bin/env bash` shebang, so the bash version under test is whatever is
  first on PATH rather than the macOS 3.2 the users hit.

### Defect 5 — no PATH-shadowing warning after linking

`install.sh`'s `link_aet_binary()` creates `~/.local/bin/aet` but never checks
whether a *different* `aet` wins on PATH afterward, so the installer reports
success while `aet` keeps resolving elsewhere. Observed live with a pyenv shim.
`aet install` warns when the bin dir is absent from PATH
(`src/aet/cli/main.py:463`), but neither path warns about shadowing — the case
where the directory *is* on PATH but loses.

## Fix Summary

**Not applied. All five defects are routed to `aet-plan`.**

An earlier draft of this section proposed in-place fixes: guard the array at its
two expansion sites, bump the version and add a release gate to catch the next
drift, add a shadowing warning. The owner rejected that framing on 2026-07-22 —
*"I asked you to PLAN a proper fix, not doing workarounds."* Those are detectors
and patches on instances of classes that should not exist.

The re-analysis found the five defects are not independent. The toolkit has
**three overlapping hand-rolled mechanisms** answering one question — how does
`aet` get onto `PATH` and run under an interpreter that can import it — and each
defect is two of them colliding:

| # | Mechanism | Defect it produced |
|---|---|---|
| 1 | `install.sh` `link_aet_binary()` | — (correct, and overwritten by 2) |
| 2 | `_ensure_path_link()` on every subcommand | defect 2: rewrites the link to a module path |
| 3 | `main.py` bootstrap guard | exists only to make 2's bad target work; fails on packaged installs |

Mechanism 3 is circular: it exists so a directly-invoked `main.py` can import its
own package, and the only artifact that invokes `main.py` directly is the symlink
mechanism 2 wrongly creates. Plus a fourth hand-rolled surface — ~90 lines of
bash flag parsing marshalling arguments for a Typer program that already parses
flags, which is where defect 1 lives.

Planned as class elimination:

- `docs/prds/fresh-install-correctness-prd.md` — R-15…R-32
- **ADR-041** — the console script is the only entry point. Deletes mechanisms 2
  and 3; `aet install` becomes `aet setup link`.
- **ADR-042** — the installer is a bootstrap. The bash boundary is
  `uv pip install`; the array is **removed, not guarded**; adds `aet setup
  verify` for defect 5.
- **ADR-043** — the version derives from the git tag (`hatch-vcs`). Explicitly
  reverses the release-gate decision taken earlier the same day: a gate detects
  the drift instead of preventing it, keeps two sources of truth, and adds a
  check to maintain in order to police a step that stays manual.

| Plan | Defect | Class removed |
|---|---|---|
| `fic-01-one-entry-point` | 2 | three PATH mechanisms → one |
| `fic-02-installer-bootstrap-boundary` | 1, 5 | bash marshalling args for a Typer program |
| `fic-03-version-from-git-tag` | 3 | two sources of truth for the version |
| `fic-04-installer-verification-coverage` | 4 | a suite that tests a configuration no user runs |

The one deliberate patch is `scripts/validate-skills.sh:26,103,141`, which gets
the `${arr[@]+"${arr[@]}"}` guard (`fic-02` task 6). It is off the installer path
and does not justify a rewrite.

If a release is needed before `fic-02` lands, the two-line array guard at
`install.sh:193,198` remains the correct **emergency** patch — verified working
in the Reproduction Steps above. It is not the fix.

### Diff Budget

The bug diff budget (≤ 3 files, ≤ 100 lines) does not apply: no defect is being
fixed under this report. Sizing lives in the four plans, each carrying its own
guardrail check.

## Regression Test

None added under this report. Required coverage is enumerated under defect 4 and
planned as `fic-04`, which is blocked by the three fix plans so it asserts their
end state. Every new test must be demonstrated failing against pre-fix code
(R-32) — defect 4 is the direct consequence of tests that only ever exercised
the passing path.

## Validation

- [ ] Reproduction steps no longer trigger the bug
- [ ] Existing test suite passes with no new failures
- [ ] No regressions observed in related functionality
- [x] Defects 1, 2, 3 reproduced with evidence on 2026-07-22
- [x] Bash-3.2-safe idiom verified working before proposing it

Security note: defect 2 concerns symlink creation in the user bin directory —
cli-04 carried `security_review: required` for exactly this reason. The
follow-up plan should inherit that flag and invoke `aet-cso` at validation.

## Lessons Learned

- **Pattern:** *deployment-model change silently invalidating a locked design.*
  cli-04's "invoked copy wins" was correct for a source-checkout script and
  wrong for a packaged console script. uvi-02 changed the deployment model and
  nothing re-examined the decisions built on the old one. Worth a sweep for
  other code still assuming `__file__` is the entry point.
- **Pattern:** *tests that only exercise the convenience path.* Every installer
  test passed a flag that happened to avoid the empty-array branch, so the
  documented default was the single untested configuration. The bug lived
  exactly where the fixtures did not go.
- **Prevention:** test the *documented* invocation verbatim — the no-flag
  one-liner is the copy users actually paste. Shell scripts distributed to end
  users should be exercised under `/bin/bash` (3.2) on macOS, not the PATH bash;
  `set -u` array expansion is not portable and needs the `[@]+` guard by
  default.
- **Prevention:** post-install verification should assert the *end state a user
  experiences* (`command -v aet`, then a real subcommand, then re-check the
  link), not the state the installer believes it created.
- **Pattern:** *narrowing a mechanism instead of removing it.*
  `.agents/learnings.jsonl` (2026-07-15) records the same self-repair mechanism
  repointing `~/.local/bin/aet` at an ephemeral `vgr-04` worktree copy. The
  proposed fix was to narrow it to reject `.worktrees/` paths; cli-04 did exactly
  that; the mechanism survived and produced 2026-07-22. A second occurrence of
  the same class is the signal to delete, not to narrow a third time.
- **Reference:** `docs/plans/cli-04-aet-install-self-repair.md` (design being
  reversed); `docs/plans/uvi-02` (installer that changed the deployment model);
  `docs/adr/041`, `042`, `043`; `docs/prds/fresh-install-correctness-prd.md`.

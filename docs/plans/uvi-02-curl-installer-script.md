---
id: uvi-02-curl-installer-script
size: M
status: queued
blocked_by:
  - uvi-01-aet-setup-skills-command
pipeline: standard
security_review: required
security_review_reason: Script downloads and executes uv installer and clones git repo; must verify checksums, refuse sudo, and only write to user-owned paths.
docs_sync: required
docs_sync_reason: README Quick Start will lead with the new one-liner.
---

# Plan: Create `scripts/install.sh` one-line installer

## Context

Part of the [uv one-line installer PRD](../prds/uv-one-line-installer-prd.md) (`docs/prds/uv-one-line-installer-prd.md`). This task creates the `curl | bash` entry point that bootstraps `uv`, clones the repo, installs the `aet` CLI, links skills via `aet setup skills`, and puts `aet` on `PATH`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `scripts/install.sh` with argument parsing for `--tag`, `--agent`, `--bin-dir`, `--skills-dir`, `--repo`, `--dry-run`, `--help` — M (traces: R-2)
2. Implement `uv` detection and bootstrap via Astral's official installer — M (traces: R-3)
3. Clone or update the AE Toolkit repo to `~/.local/share/ae-toolkit` and checkout the requested tag — M (traces: R-4)
4. Install `aet` from the cloned repo into a dedicated venv at `~/.local/share/ae-toolkit/venv` using `uv venv` + `uv pip install` — M (traces: R-5)
5. Invoke `aet setup skills` from the installed binary for the selected agent(s) — M (traces: R-6, R-7, R-8)
6. Symlink `<bin-dir>/aet` to the venv console script (`~/.local/share/ae-toolkit/venv/bin/aet`) directly from the script — never invoking `aet install`, whose `Path(__file__)` link target only resolves on the editable dev path — and never linking a worktree copy — S (traces: R-8, R-9)
7. Add idempotency, error handling, and a final summary — S (traces: R-10, R-11)
8. Run shellcheck on the script and fix warnings — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Batching Check

- [x] This is not one of several near-identical additions
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] The work cannot share a branch/PR with unrelated tasks

## Rejected Alternatives

- **Publish to PyPI and use `uv tool install aet`** — rejected: PyPI publishing is out of scope for this PRD; the installer must also deliver skills, which `uv tool install` cannot bundle.
- **Install skills with `npx skills add`** — rejected: requires Node/npm and still leaves the user with a separate tool to install; direct symlink is simpler and agent-agnostic.
- **Edit shell profiles automatically** — rejected: the existing `aet install` deliberately keeps this manual; auto-editing profiles is error-prone and outside the trust boundary.

## Files to Modify

- `scripts/install.sh` — new installer script
- `Makefile` — add `test-installer` or wire into `validate`
- `README.md` — update Quick Start with the one-liner

## Validation Steps

- [ ] `scripts/install.sh --help` prints usage without network access
- [ ] `scripts/install.sh --dry-run` prints all planned actions and modifies no files
- [ ] ShellCheck passes on `scripts/install.sh`
- [ ] The script exits non-zero on invalid arguments
- [ ] `make validate` passes (if the script is wired into it)
- [ ] For the new `scripts/install.sh` file, the smoke test in `uvi-03-installer-smoke-test` covers it
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task; no task cites an unknown R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the commit and remove the README one-liner; the manual pip path remains documented and functional.

---

_Stage: secure_
_Next step: run `aet-sync-docs`, then `aet-ship`_

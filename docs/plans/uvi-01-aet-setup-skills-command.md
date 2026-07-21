---
id: uvi-01-aet-setup-skills-command
size: M
status: queued
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: Skill symlinking writes to ~/.*/skills directories; must not follow untrusted symlinks or overwrite user data unexpectedly.
docs_sync: required
docs_sync_reason: README and AGENTS.md install instructions may need updates after this command exists.
---

# Plan: Add `aet setup skills` CLI command

## Context

Part of the [uv one-line installer PRD](../prds/uv-one-line-installer-prd.md) (`docs/prds/uv-one-line-installer-prd.md`). The installer needs a deterministic, testable way to symlink AE Toolkit skills into agent directories, mirroring what `make install-skills` does today but callable from a shell script without `make`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Add a `setup` Typer sub-app under `aet` with a `skills` command — M (traces: R-6, R-7)
2. Implement agent-directory discovery and skill symlink logic — M (traces: R-6, R-7)
3. Add CLI options for `--skills-dir`, `--agent`, `--dry-run`, and `--force` — S (traces: R-2, R-10)
4. Wire the command into `src/aet/cli/main.py` and ensure `--help` works — S (traces: R-1)
5. Add unit tests for discovery and symlink logic using temporary directories — M (traces: R-6, R-7)
6. Run `make validate` and fix any lint/test failures — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Batching Check

- [x] This is not one of several near-identical additions
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] The work cannot share a branch/PR with unrelated tasks

## Rejected Alternatives

- **Inline skill linking in `scripts/install.sh`** — rejected: duplicating the `make install-skills` logic in shell makes it hard to test and lint; a CLI command keeps it in Python where it can share helpers with `aet install`.
- **Extend `aet install` to also handle skills** — rejected: `aet install` currently owns PATH binary linking; mixing skill content linking would overload its semantics and complicate testing. A separate `aet setup skills` command is clearer.

## Files to Modify

- `src/aet/cli/setup.py` — new file with the `setup skills` command
- `src/aet/cli/main.py` — register the new sub-app
- `tests/cli/test_setup_skills.py` — new tests for discovery and symlink behavior
- `README.md` — document `aet setup skills` as the manual skill-install path

## Validation Steps

- [ ] `aet setup skills --help` prints usage
- [ ] `aet setup skills --dry-run --agent generic --skills-dir <tmp>` lists planned symlinks without writing
- [ ] `aet setup skills --skills-dir <tmp>` creates symlinks for every `skills/*` directory
- [ ] Re-running the command is idempotent
- [ ] `make validate` passes (ruff, pytest, skills-lint)
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task; no task cites an unknown R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the commit; the `setup` subcommand removal is safe because no existing workflow depends on it until the installer PR lands.

---

_Stage: secure_
_Next step: run `aet-sync-docs`, then `aet-ship`_

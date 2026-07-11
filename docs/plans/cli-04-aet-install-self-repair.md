---
id: cli-04-aet-install-self-repair
size: M
blocked_by:
  - cli-01-aet-multicall-dispatcher
pipeline: standard
status: approved
security_review: required
security_review_reason: creates and removes symlinks in the user bin directory; path-resolution and prune-target correctness are security-relevant
docs_sync: skipped
docs_sync_reason: bootstrap documentation is rewritten in cli-05 together with the rest of the surface
---

# Plan: `aet install` and On-Invocation Self-Repair

## Context

- PRD: `docs/prds/roadmap-p2-aet-binary-prd.md` (G1, G3; R-5 install mechanics, R-11, plus R-10 tests)
- Split from: cli-01 (session-size limit). Dissolves the owner's gate feedback (2026-07-11): the standalone `install-aet-binaries` confused multiple times — a rarely-run manual step whose omission surfaces later as `command not found`. After this task, the binary owns its own PATH link; toolkit updates never require re-running an installer.
- Additive: the standalone installer script still exists and works; cli-05 deletes it and rewires Makefile/aet-setup bootstrap to `aet install`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **`aet install`** (`install` row added to `SUBCOMMANDS`, the one internal-mode subcommand per R-1): links `AET_BIN_DIR` (default `~/.local/bin`, `--bin-dir` flag override, `mkdir -p`) `/aet` → the resolved running script; replaces a stale AET-managed symlink; refuses a non-symlink collision with a warning (the existing installer's semantics); prints the exact `export PATH=…` line when the bin dir is not on PATH — shell profiles are never edited.
- **Prune, gated**: `LEGACY_NAMES = ("aet-work", "aet-state", "aet-retro", "orchestrator", "mine-learnings", "configure-task-backend", "install-aet-binaries")` implemented behind `--prune` (opt-in at this task). cli-05 makes pruning unconditional — the flip is a one-line default change plus test update. Pruning only removes symlinks that resolve into a skills directory (the existing installer's `_points_into_skill_dir` guard, ported), never foreign files.
- **Self-repair (R-11)**: `_ensure_path_link()` at dispatcher startup — one `readlink`; creates or repairs `AET_BIN_DIR/aet` when missing or pointing at a different checkout (invoked copy wins; `AET_SKILLS_DIR`/`AET_BIN_DIR` dev overrides respected); silent, best-effort, never fatal, never touches anything but the AET-managed `aet` symlink, skipped on the `install` subcommand itself (which reports verbosely).
- Tests isolate via `AET_BIN_DIR` pointed at a temp dir — no test writes to the real `~/.local/bin`.

## Rejected Alternatives

- **Keeping a standalone installer script** — rejected (owner gate feedback): link management belongs inside the binary that owns the link; self-repair removes the "forgot to re-run it" failure mode entirely.
- **Auto-editing shell profiles for PATH membership** — rejected: silently mutating user shell config is the wrong kind of magic; a one-line warning with the exact export line is the honest interface.
- **Self-repair only warning instead of fixing** — rejected: a warning is another thing to remember; the fix is idempotent, scoped to one AET-owned symlink, and reversible.
- **Unconditional prune in this task** — rejected: skills still reference legacy names until cli-05's rewrite; pruning now would break the running system mid-phase (additive-then-flip).

## Task List

1. `install` subcommand: link/replace/collision/PATH-warning, `--bin-dir`, gated `--prune` with the skills-dir guard — M (traces: R-5)
2. `_ensure_path_link()` self-repair on dispatcher startup — S (traces: R-11)
3. Write `tests/test_aet_install.py`: fresh link; stale-link repair to the invoked copy; non-symlink collision skipped with warning; prune removes exactly the seven names and only skills-dir-resolving links; idempotency (second run is a no-op); self-repair restores a deleted link and never runs on `install` itself; `AET_BIN_DIR` isolation — M (traces: R-10)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition — installer semantics, distinct from dispatch (cli-01); split for session size, not by preference
- [x] Diff expected > 50 lines
- [x] Cannot share a branch with cli-01 — recombining recreates the oversized session the split exists to avoid

## Files to Modify

- `aet-work/bin/aet`
- `tests/test_aet_install.py` (new)

## Validation Steps

- [ ] `make validate` passes
- [ ] Named tests per new source file: `tests/test_aet_install.py` → `install` behaviors + self-repair (unit against temp bin dir; integration: subprocess `aet install --bin-dir <tmp>` then `aet status` self-repair after link deletion)
- [ ] R-trace coverage: R-5 by task 1; R-11 by task 2; R-10 by task 3; no unknown R-ids cited
- [ ] Manual spot-check in a worktree: delete the temp link, run `aet` by path, observe the link restored; confirm real `~/.local/bin` untouched by the suite
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. `install` and self-repair are additive to a binary nothing references yet; the standalone installer remains the live bootstrap until cli-05.

---

_Stage: implemented_
_Next step: run `aet-qa`_

---
id: ewl-03-hooks-install-pre-push
size: M
blocked_by:
  - cli-03-skills-lint
  - uct-01-usage-cost-telemetry
pipeline: standard
security_review: required
security_review_reason: modifies and installs the pre-push hook that gates what reaches the remote — hook-bypass, install-path errors, or an incomplete task-branch check would silently defeat the enforcement wall this plan exists to build
docs_sync: required
docs_sync_reason: replaces docs/CONVENTIONS.md's manual symlink instructions with a new aet hooks install command; the bootstrap step documented today changes
---

# Plan: `aet hooks install` — Pre-Push Gate-Evidence Enforcement

## Context

- PRD: `docs/prds/roadmap-p3-enforcement-walls-prd.md` (G2; R-4, plus R-7a/R-8 tests)
- `scripts/hooks/pre-push` (waf-05, merged) already short-circuits on pure branch-deletion pushes and otherwise runs the full test+coverage gate. Installing it today is a manual symlink step documented in `docs/CONVENTIONS.md`.
- This plan extends that existing hook — it does not replace it — with a check that a task branch cannot be pushed unless its task has recorded gate evidence for its required stages, and formalizes installation as `aet hooks install`.
- cli-01's `aet` dispatcher already has a precedent for a binary with its own internal subcommands reached through the top-level table (e.g., `state` → `aet-state`'s own subparsers for `audit`/`heal`/etc.) — `hooks install` follows that same shape rather than inventing a new dispatch mode.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `scripts/hooks/pre-push` gains a task-branch check, inserted after the existing deletion short-circuit and before (or alongside) the coverage gate:
  1. Detect whether the branch being pushed is a task branch, reusing whatever convention `aet-ship`/`aet-work` already use to derive a task's branch name from its plan ID (worktree naming) — not a new heuristic.
  2. If it is a task branch, resolve the task's plan frontmatter (`security_review`, `docs_sync`) to determine its required stages (core `qa`/`review` always required; `cso` required unless `security_review: skipped`; `sync-docs` required unless `docs_sync: skipped`).
  3. For each required stage, check recorded gate evidence (via `evidence.read_verdict`) is present and `pass`. Any missing or failing required stage refuses the push with a named, per-stage error listing exactly what's missing.
  4. Non-task-branch pushes and the existing coverage gate behavior are unchanged.
- New `aet-setup/bin/hooks` (stdlib-only Python, own argparse subcommands — `install` is the first): symlinks `scripts/hooks/pre-push` into `.git/hooks/pre-push`, idempotent (safe to re-run, detects and leaves a pre-existing non-AET hook alone with a warning rather than clobbering it).
- `aet`'s `SUBCOMMANDS` table gains `"hooks": {"target": ("aet-setup", "hooks"), "mode": "exec"}` — `aet hooks install` execs `aet-setup/bin/hooks` with `install` forwarded as an argument, matching the `state`-style nested-subcommand precedent. The target passes the **bare** bin-name `"hooks"`, not `"bin/hooks"`: `_resolve_target` (`aet-work/bin/aet:104`) already appends `bin/`, so a prefixed value would resolve to `aet-setup/bin/bin/hooks`.
- `docs/CONVENTIONS.md`'s manual symlink instructions are replaced with `aet hooks install`.

## Rejected Alternatives

- **Replace `scripts/hooks/pre-push` wholesale with a new script** — rejected: waf-05's deletion short-circuit and coverage gate are working, reviewed behavior; extending preserves that investment and keeps the diff reviewable as "what changed" rather than "what's new."
- **A new heuristic for detecting task branches** — rejected: `aet-ship`/`aet-work` already have one; a second, slightly different heuristic is exactly the kind of drift the PRD's "CLI is the only legitimate writer" principle is trying to eliminate elsewhere.
- **Fold `hooks install` into `aet install`'s self-repairing bootstrap (cli-04)** — rejected (recorded as an Open Question in the PRD): git hooks are repo-local, `aet install`'s PATH link is global; bundling isn't obviously correct and isn't blocking for this phase.

## Task List

1. Extend `scripts/hooks/pre-push` with the task-branch gate-evidence check per Locked design, preserving waf-05's deletion short-circuit and coverage-gate behavior — M (traces: R-4)
2. Write `aet-setup/bin/hooks` with an `install` subcommand (idempotent symlink into `.git/hooks/pre-push`); add the `hooks` row to `aet`'s `SUBCOMMANDS` table — M (traces: R-4)
3. Update `docs/CONVENTIONS.md`: replace the manual symlink instructions with `aet hooks install` — S (traces: R-4)
4. Tests: `tests/test_hooks_install.py` (new, covers the `install` subcommand's idempotency and non-clobber behavior) — M (traces: R-4, R-8)
5. Manual validation: on a task branch with an unrecorded required gate, `git push` is refused by the installed hook; a branch with all required gates recorded pushes cleanly — S (traces: R-4, partial R-7a)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition to anything queued
- [x] Diff expected > 3 files / > 100 lines (hook extension + new binary + dispatcher row + docs + tests)
- [x] Cannot share a branch with ewl-01/ewl-04/ewl-05 — distinct files, distinct risk surface (git hook installation)

## Files to Modify

- `scripts/hooks/pre-push`
- `aet-setup/bin/hooks` (new)
- `aet-work/bin/aet`
- `docs/CONVENTIONS.md`
- `tests/test_hooks_install.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_hooks_install.py`:
  - `test_install_symlinks_pre_push_hook`
  - `test_install_is_idempotent_on_rerun`
  - `test_install_warns_and_does_not_clobber_existing_non_aet_hook`
  - `test_hooks_install_routed_through_aet_dispatcher`
- [ ] Manual validation (task 5) executed and result recorded in this plan before merge
- [ ] R-trace coverage: R-4 by tasks 1–3, 5; R-8 by task 4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. `scripts/hooks/pre-push` returns to waf-05's deletion-short-circuit-plus-coverage-gate behavior; already-installed hooks from this plan keep running the extended check until manually re-symlinked to the reverted script (documented as a known rollback caveat, not auto-handled).

## Pipeline

`pipeline: standard`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_

---
id: ewl-03-hooks-install-pre-push
size: M
blocked_by:
  - cli-03-skills-lint
  - uct-01-usage-cost-telemetry
pipeline: standard
security_review: required
security_review_reason: generates and installs the pre-push hook that gates what reaches the remote — hook-bypass, install-path errors, or an incomplete task-branch check would silently defeat the enforcement wall this plan exists to build
docs_sync: required
docs_sync_reason: replaces docs/CONVENTIONS.md's manual symlink instructions with a new aet hooks install command; the bootstrap step documented today changes
---

# Plan: `aet hooks install` — Pre-Push Gate-Evidence Enforcement

## Context

- PRD: `docs/prds/roadmap-p3-enforcement-walls-prd.md` (G2, G5; R-4, plus R-7a/R-8 tests)
- `scripts/hooks/pre-push` (waf-05, merged) short-circuits pure branch-deletion pushes and otherwise runs the full test+coverage gate (`make validate`). Installing it today is a manual symlink step documented in `docs/CONVENTIONS.md`.
- **Mode 1 changes the install model.** Phase 3 must be installable on a repo whose team does not use AET, committing nothing about AET (PRD G5/R-9/R-10). Symlinking a _tracked_ `scripts/hooks/pre-push` fails that: it requires that file to exist in the repo. So `aet hooks install` now **generates a self-contained hook** that calls the globally-installed `aet` binary (cli-04's PATH link) — no committed repo file needed — and the AET responsibility narrows to gate-evidence enforcement, never imposing a repo-specific build/coverage gate on the team's pushes.
- cli-01's `aet` dispatcher already has a precedent for a binary with its own internal subcommands reached through the top-level table (e.g., `state` → `aet-state`'s own subparsers) — `hooks install` / `hooks check` follow that same shape.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **`aet hooks install` generates a self-contained `.git/hooks/pre-push`** rather than symlinking a committed script. The installed hook is a thin shim that (1) short-circuits pure branch-deletion pushes, (2) runs the AET gate-evidence check via the globally-installed `aet` binary, and (3) chains to an optional repo-local `scripts/hooks/pre-push` _if one exists_, so a repo can still layer its own coverage gate. Nothing about the hook requires an AET file committed to the repo — the Mode-1 requirement (R-9/R-10) that makes this phase installable on a client's repo.
- **Gate-evidence check as `aet hooks check`** (new subcommand in `aet-setup/bin/hooks`, stdlib-only): reads the pushed refs from stdin (git's pre-push protocol), and for each ref on a **task branch**:
  1. Detect the task branch reusing whatever convention `aet-ship`/`aet-work` already use to derive a task's branch name from its plan ID (worktree naming) — not a new heuristic.
  2. Resolve the task's plan frontmatter (`security_review`, `docs_sync`) to its required stages (core `qa`/`review` always; `cso` unless `security_review: skipped`; `sync-docs` unless `docs_sync: skipped`).
  3. For each required stage, verify recorded gate evidence (`evidence.read_verdict`) is present and `pass`. Any missing/failing required stage exits non-zero with a named, per-stage error listing exactly what is missing.
  - Non-task-branch pushes: no-op (exit 0). The check imposes **no** build/coverage gate of its own — that stays the optional chained companion's job, so `aet hooks install` never forces a repo-specific gate onto a team that does not use AET.
- **`aet-setup/bin/hooks`** (new, own argparse subcommands): `install` (writes the shim; idempotent; detects and leaves a pre-existing non-AET hook alone with a warning rather than clobbering; rewrites a prior AET shim in place) and `check` (the stdin-driven evidence check above).
- **`aet`'s `SUBCOMMANDS` table gains `"hooks": {"target": ("aet-setup", "hooks"), "mode": "exec"}`** — `aet hooks install` / `aet hooks check` exec `aet-setup/bin/hooks` with the nested subcommand forwarded, matching the `state`-style nested-subcommand precedent. The target passes the **bare** bin-name `"hooks"`, not `"bin/hooks"`: `_resolve_target` (`aet-work/bin/aet:104`) already appends `bin/`, so a prefixed value would resolve to `aet-setup/bin/bin/hooks`.
- **`scripts/hooks/pre-push`** is reduced to the optional repo-local coverage companion (its `make validate` gate, for aiskills' own self-hosting), which the generated shim chains to when present — it is no longer the installed artifact.
- `docs/CONVENTIONS.md`'s manual symlink instructions are replaced with `aet hooks install`.

## Rejected Alternatives

- **Symlink the tracked `scripts/hooks/pre-push` into `.git/hooks` (waf-05's install model)** — rejected: it couples the installed hook to a committed repo file, so it cannot work in a Mode-1 client repo that commits nothing about AET (R-9/R-10). Generating a self-contained shim that calls the global `aet` binary removes the coupling; the clean cut (no dual symlink/generate mechanism) matches the project's no-backward-compat rule.
- **Inline the full evidence-check logic in the generated hook body** — rejected: the hook would freeze whatever logic existed at install time; delegating to `aet hooks check` in the versioned toolkit lets the check evolve with the toolkit and keeps the shim a few lines.
- **A new heuristic for detecting task branches** — rejected: `aet-ship`/`aet-work` already have one; a second, slightly different heuristic is exactly the kind of drift the PRD's "CLI is the only legitimate writer" principle is trying to eliminate elsewhere.
- **Fold `hooks install` into `aet install`'s self-repairing bootstrap (cli-04)** — rejected (recorded as an Open Question in the PRD): git hooks are repo-local, `aet install`'s PATH link is global; bundling isn't obviously correct and isn't blocking for this phase.

## Task List

1. Add `aet hooks check` to a new `aet-setup/bin/hooks` (stdin-driven task-branch gate-evidence check per Locked design; named per-stage errors; no-op on non-task branches) — M (traces: R-4)
2. Add `aet hooks install` to `aet-setup/bin/hooks`: generate the self-contained `.git/hooks/pre-push` shim (deletion short-circuit → `aet hooks check` → chain to optional repo-local `scripts/hooks/pre-push`); idempotent; non-clobbering of a pre-existing non-AET hook; add the `hooks` row to `aet`'s `SUBCOMMANDS` table — M (traces: R-4)
3. Reduce `scripts/hooks/pre-push` to the optional repo-local coverage companion (`make validate`), chained-when-present; update `docs/CONVENTIONS.md` to replace the manual symlink instructions with `aet hooks install` — S (traces: R-4)
4. Tests: `tests/test_hooks_install.py` (new) — install idempotency, non-clobber, install-with-no-committed-`scripts/hooks/pre-push`, chain-to-companion-when-present, dispatch routing, and `aet hooks check` refusing/allowing per recorded evidence — M (traces: R-4, R-8)
5. Manual validation: (a) on a task branch with an unrecorded required gate, `git push` is refused; a fully-recorded branch pushes cleanly; (b) in a scratch repo with **no** committed `scripts/hooks/pre-push`, `aet hooks install` still yields a working gate-evidence hook — S (traces: R-4, partial R-7a)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition to anything queued
- [x] Diff expected > 3 files / > 100 lines (new bin with two subcommands + dispatcher row + hook-script reduction + docs + tests)
- [x] Cannot share a branch with ewl-01/ewl-04/ewl-05/ewl-07 — distinct files, distinct risk surface (git hook installation)

## Files to Modify

- `aet-setup/bin/hooks` (new)
- `aet-work/bin/aet`
- `scripts/hooks/pre-push`
- `docs/CONVENTIONS.md`
- `tests/test_hooks_install.py` (new)

## Validation Steps

- [x] `make validate` passes; full suite passes (592 passed, 2026-07-14)
- [x] New source coverage — `tests/test_hooks_install.py` (9 tests, all green):
  - `test_install_generates_self_contained_pre_push_hook`
  - `test_install_works_with_no_committed_scripts_hook`
  - `test_install_is_idempotent_on_rerun`
  - `test_install_warns_and_does_not_clobber_existing_non_aet_hook`
  - `test_generated_hook_chains_to_repo_local_script_when_present`
  - `test_hooks_check_refuses_task_branch_missing_required_gate`
  - `test_hooks_check_allows_task_branch_with_all_gates_recorded`
  - `test_hooks_check_noop_on_non_task_branch`
  - `test_hooks_install_routed_through_aet_dispatcher`
- [x] Manual validation (task 5), both (a) and (b), executed 2026-07-14 in a scratch Mode-1 repo (result below)
- [x] R-trace coverage: R-4 by tasks 1–3, 5; R-8 by task 4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

### Manual validation result (2026-07-14)

Executed in a scratch repo with **no committed `scripts/hooks/pre-push`** (Mode-1 non-invasive install) and a bare `origin`:

- **(a) gate refusal/allowance** — on task branch `demo-task` (plan with `security_review: required`, `docs_sync: skipped`) with `qa`+`review` verdicts recorded but `cso` missing: `git push` was **refused** with `task 'demo-task': required gate 'cso' (stage 'reviewed') — no verdict recorded at <path>`; `demo-task` did not reach the remote. After recording the `cso` pass verdict, the push **succeeded**.
- **(b) no committed companion** — with no `scripts/hooks/pre-push` in the repo, `aet hooks install` still produced a working gate-evidence hook (the refusals/allowances above ran through it; the companion chain was skipped as designed). A non-task branch (`main`, no verdicts) pushed cleanly as a no-op.

## Rollback Plan

Revert the merge commit. `aet hooks install`/`aet hooks check` and the generated-shim behavior are removed; `scripts/hooks/pre-push` returns to waf-05's deletion-short-circuit-plus-coverage-gate content. Already-installed generated shims in developer clones keep calling `aet hooks check` until re-run or removed (documented as a known rollback caveat, not auto-handled).

## Pipeline

`pipeline: standard`.

---

_Stage: secure_
_Next step: run `aet-sync-docs`, then `aet-ship`_

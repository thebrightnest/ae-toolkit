---
id: ewl-04-git-refs-default-flip
size: S
blocked_by: []
pipeline: standard
security_review: skipped
security_review_reason: changes a default in an install-time config writer plus messaging — no new code path or trust boundary; both backends are already implemented, parity-tested (frh-13/14), and git-refs gained tamper-evidence in ewl-05 (merged)
docs_sync: required
docs_sync_reason: configure-task-backend messaging, aet-setup Step 6 docs, and the factory docstring currently describe git-refs as "prototype, opt-in" — that framing becomes incorrect once aet-setup writes it by default; ADR-014's consequence "JSON is the default backend" remains true for unconfigured projects (factory fallback unchanged) and must be annotated, not reversed, to record the setup-layer default
---

# Plan: git-refs Becomes the Default Task-Storage Backend

## Context

- PRD: `docs/prds/roadmap-p3-enforcement-walls-prd.md` (G3, and the storage half of G5; R-5, plus R-8 tests)
- **Revised 2026-07-14 (option A — configure-layer default).** The original locked design flipped the no-config fallback in `aet-work/lib/backends/factory.py` to `GitRefsBackend`. At implement time that was measured infeasible: the suite went **583 → 481 passed (103 failures)** because `GitRefsBackend.__init__` runs `git rev-parse --show-toplevel` and raises `RuntimeError` outside a git repo — ~100 tests construct the default backend in non-git temp dirs — and `tests/test_read_path_no_git.py` mocks git to fail on any git call on the status/next read path, an invariant a git-refs factory default breaks by construction. The factory fallback must stay `json`.
- **The original premise was also inaccurate:** "a genuinely fresh install has no `.agents/aet-work.json`" — aet-setup Step 6 runs `aet configure-backend`, which _writes_ that file (`aet-setup/SKILL.md:178`; `aet-setup/checklist.md` verifies it exists with a valid `task_backend`). The real fresh-install path is therefore the **written** default, not the factory fallback — which is exactly where this revision puts the flip.
- `aet-setup/bin/configure-task-backend` currently has no default: interactive mode prompts, non-interactive mode errors without `--backend`, and its messaging frames git-refs as a "prototype, opt-in … not recommended for production queues yet". That framing is now stale twice over: this plan makes git-refs the written default, and ewl-05 (merged) gave the backend tamper-evidence, removing the integrity-gap caveat the original design worried about.
- This plan does not remove the JSON backend (explicit Non-Goal in the PRD): it remains the factory fallback for unconfigured/non-git contexts and an explicit `task_backend: "json"` opt-out. **Why git-refs as the written default also serves Mode 1 (PRD G5):** git-refs keeps the queue and history in `.git` (`refs/aet/tasks/*`, `refs/aet/meta/queue`) — local-only/unpushed per frh-13, invisible to `git status` and never in the shared tree; a Mode-1 project's task state needs no working-tree file and no `.gitignore` entry at all. This plan does **not** touch the local-only push policy (team-shared ledger is Mode 2, roadmap doc 09 Phase 6, out of scope).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `aet-setup/bin/configure-task-backend`: when `--backend` is **not** supplied, default the written config to `task_backend: "git-refs"` — interactive mode offers git-refs as the default choice (empty input accepts it), and non-interactive mode no longer errors on a missing `--backend` but writes git-refs. Explicit `--backend json|github|git-refs` behaves exactly as today. This is the only behavioral change.
- Same file, messaging: present git-refs as the default/recommended backend and JSON as the documented opt-out/fallback; remove the "prototype, opt-in … not recommended for production" NOTE (usage text, the `--backend` help line, and the NOTE emitted on git-refs selection). A short NOTE on `--backend json` explaining when the opt-out is appropriate (non-git or unconfigured contexts) replaces it.
- `aet-work/lib/backends/factory.py`: **no logic change** — the no-config fallback stays `json`. Docstring framing only: git-refs is what aet-setup writes by default; `json` remains the fallback for unconfigured or non-git contexts.
- `aet-setup/SKILL.md` Step 6 (and `aet-setup/checklist.md` if it names a default): document git-refs as the default written backend, JSON as opt-out.
- No change to `GitRefsBackend` or `JsonBackend` implementations.

## Rejected Alternatives

- **Factory-level default flip (the original locked design)** — rejected with measured evidence: 103 suite failures (583 → 481) from `GitRefsBackend`'s git-repo construction requirement in non-git test contexts, plus a broken read-path no-git invariant (`tests/test_read_path_no_git.py`). R-5's acceptance criterion targets a fresh `aet-setup` run, which writes config — the factory fallback is the wrong layer.
- **Git-detection fallback in factory** (git-refs when the queue path is inside a git repo, else json) — rejected: a silent, context-dependent default in a load-bearing factory is harder to reason about and test than an explicit written config; the configure layer already makes the choice visible and recorded.
- **Remove `JsonBackend` entirely** — rejected: explicit Non-Goal in the PRD; existing installs that pinned `task_backend: "json"` must keep working, and the parity suite depends on both backends still being real, selectable code paths.
- **Bundle the tamper-evidence work (R-6) into this plan** — rejected and now moot: R-6 landed as ewl-05 (merged 2026-07-14).

## Task List

1. `aet-setup/bin/configure-task-backend`: default the no-`--backend` path to `git-refs` (interactive + non-interactive); flip messaging to default-vs-opt-out; remove the prototype NOTE — S (traces: R-5)
2. `aet-work/lib/backends/factory.py` docstring + `aet-setup/SKILL.md` Step 6 (+ `checklist.md` if applicable): document the setup-layer default; factory fallback stays `json` — S (traces: R-5)
3. `tests/test_aet_setup_backend_config.py`: update `test_git_refs_backend_creates_config_and_notes_prototype` (prototype framing removed); add a no-flag test asserting the written config selects `git-refs`; add a factory assertion that the no-config fallback remains `JsonBackend` (guards against regression toward the rejected factory flip) — S (traces: R-5, R-8)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition to anything queued
- [x] Diff expected ≤ 80 lines / 4 files
- [x] Cannot share a branch with ewl-05 — this changes the default selection, ewl-05 changed the backend's internal integrity mechanism (merged); independently revertible

## Files to Modify

- `aet-setup/bin/configure-task-backend`
- `aet-work/lib/backends/factory.py` (docstring only)
- `aet-setup/SKILL.md` (+ `aet-setup/checklist.md` if it names a default)
- `tests/test_aet_setup_backend_config.py`

## Validation Steps

- [ ] `make validate` passes; full suite passes (must hold 583+ green — the factory-flip regression measured 481)
- [ ] New no-flag test: `configure-task-backend` with no `--backend` writes `task_backend: "git-refs"` (non-interactive) — guards R-5's fresh-install acceptance criterion
- [ ] Updated messaging test: git-refs selection emits no "prototype/opt-in/not recommended" framing
- [ ] New factory assertion: no-config fallback still returns `JsonBackend` (the rejected factory flip cannot silently return)
- [ ] `tests/test_read_path_no_git.py` green (named explicitly — it broke under the factory flip)
- [ ] Manual: a fresh `aet-setup` run with no prior config yields git-refs as the active backend (satisfies PRD acceptance criterion for R-5)
- [ ] R-trace coverage: R-5 by tasks 1–3; R-8 by task 3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — the no-flag configure path returns to requiring an explicit `--backend`, and messaging returns to the old framing. Installs that already picked up the git-refs default keep working (git-refs remains a valid explicit choice); the factory fallback was never changed, so unconfigured and non-git contexts are unaffected either way.

## Pipeline

`pipeline: standard`.

---

_Stage: implemented (2026-07-14 — tasks 1–3: configure-layer git-refs default + messaging flip, factory docstring, SKILL.md Step 6, checklist.md; 4 tests added/updated in tests/test_aet_setup_backend_config.py; make validate green, full suite 640 passed; manual fresh-dir run writes git-refs)_
_Next step: run `aet-qa`_

---
id: thp-02-worktree-project-slug
size: M
blocked_by: []
pipeline: standard
status: merged
security_review: required
security_review_reason: slug output becomes archive filesystem path segments (mkdir under ~/.aet); derivation shells out to git — verify no path-escaping or injection through crafted worktree names
docs_sync: required
docs_sync_reason: telemetry guide's slug/identity description changes from origin-remote to local-worktree identity
---

# Plan: Worktree-based Project Slug

## Context

- PRD: `docs/prds/telemetry-hygiene-plan-panel-prd.md` (R-2)
- Today `derive_project_slug()` (`aet-work/lib/telemetry.py:65`) takes the last two segments of the git **origin URL**, so this repo files under `thebrightnest/ae-toolkit` — a name the owner doesn't recognize. Decided redesign (panel README "Project slug redesign"): slug = `<main-worktree-dir>/<current-worktree-dir>`, primary worktree labelled `main`.
- Safety property already verified: the orchestrator pins `AET_REPO_ROOT` into every child env and `resolve_repo_root()` (`telemetry.py:41`) honors it before asking git — so a run's identity is always the orchestrator's launch root and stage sessions cannot scatter across per-task worktree slugs.
- Env overrides `AET_PROJECT_ID` / `AET_REPO_SLUG` remain the escape hatch (and the way to merge two clones into one project).
- **Second slug consumer (validation finding)**: gate evidence paths `{reports}/{slug}/{task-id}/` share this function (`aet-work/lib/evidence.py:96`; orchestrator passes the slug at `bin/orchestrator:319,418`). No evidence-code change is needed — identity stays consistent because every consumer calls the one function — but verdicts written before migration sit under the old slug until thp-03 renames both roots. Gates are fail-closed, so at worst a stage re-runs; do not "fix" this here.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

Rewrite the git branch of `derive_project_slug()` (env-override and non-git fallback branches unchanged):

```python
repo_root = resolve_repo_root(repo_root)
# git rev-parse --git-common-dir, cwd=repo_root; may be relative -> resolve against repo_root
common = Path(out) if os.path.isabs(out) else (repo_root / out)
main_root = common.resolve().parent          # <main>/.git -> <main>
label = "main" if repo_root == main_root else repo_root.name
return f"{main_root.name}/{label}"
```

- Primary worktree → `aiskills/main`; linked worktree `.worktrees/aet-panel` → `aiskills/aet-panel`.
- `git` missing or not a repo (`rev-parse` non-zero) → fall back to `repo_root.name` exactly as today.
- Accepted trade-offs (decided, restate in docs): two clones of one repo = two projects; two unrelated repos with the same dir name under different parents = merged; folder move/rename starts fresh. Submodules out of scope (PRD non-goal).
- Two-segment shape is preserved, so the panel's folder/project grouping (`index.html:612-615`) and `aet-work report --project` need **no change**.

## Rejected Alternatives

- **Keeping origin-remote identity with a rename map** — rejected: the panel is a local single-machine tool; local-path identity is the decided design and per-worktree grouping is a feature, not an accident.
- **`git rev-parse --show-toplevel` of the main worktree via `--path-format`** — rejected: `--git-common-dir` + parent is available on all modern git and avoids a second subprocess.
- **Folding the archive migration into this plan** — rejected: keeps this at M and separates lib semantics (reviewed as code) from a one-shot operational script (thp-03).

## Task List

1. ✓ Rewrite the git branch of `derive_project_slug()` in `aet-work/lib/telemetry.py` per Locked design; keep env-override and non-git fallbacks byte-compatible — S (traces: R-2)
2. ✓ Add `TestDeriveProjectSlug` to `tests/test_telemetry.py` with the four named cases (below), building real tmp repos via `git init` + `git worktree add` — M (traces: R-2)
3. ✓ Update `docs/telemetry-guide.md` "What gets recorded": slug definition, `main` label, override semantics, accepted trade-offs — S (traces: R-2)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition to anything queued
- [x] Diff ~150 lines / 3 files
- [x] Cannot share a branch with thp-03/thp-04 — they are blocked on this plan's merged semantics (same `telemetry.py`)

## Files to Modify

- `aet-work/lib/telemetry.py`
- `tests/test_telemetry.py`
- `docs/telemetry-guide.md`

## Validation Steps

- [x] `tests/test_telemetry.py::TestDeriveProjectSlug::test_primary_worktree_slug` — unit: tmp repo `foo/` → `foo/main`
- [x] `tests/test_telemetry.py::TestDeriveProjectSlug::test_linked_worktree_slug` — unit: `git worktree add .worktrees/bar` → `foo/bar`
- [x] `tests/test_telemetry.py::TestDeriveProjectSlug::test_env_override_wins` — unit: `AET_PROJECT_ID=x/y` → `x/y` (monkeypatched)
- [x] `tests/test_telemetry.py::TestDeriveProjectSlug::test_non_git_dir_falls_back_to_name` — unit: plain tmp dir → its basename
- [x] Full suite green (isolation fixture from thp-01 keeps these spawns out of the real archive if it merged first; tests here use tmp archives regardless)
- [x] Manual (QA stage): `python3 -c` invocation from repo root prints `aiskills/main`, from `.worktrees/aet-panel` prints `aiskills/aet-panel` — verified via the thp-02 worktree instead (aet-panel no longer exists): `aiskills/main` from main root, `aiskills/thp-02-worktree-project-slug` from the linked worktree
- [x] R-trace coverage: R-2 by tasks 1–3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — slug derivation returns to origin-remote identity; new runs file under old names again (archive dirs themselves are untouched by this plan).

---

_Stage: merged_
_Next step: run `aet-work`_

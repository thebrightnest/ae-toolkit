---
id: lop-02-plan-overlay-and-branch-seeding
size: M
work_class: normal
blocked_by: [lop-01-unpublished-plan-intake-and-hygiene]
pipeline: standard
status: queued
security_review: required
security_review_reason: introduces an orchestrator-created git commit inside the task worktree; a staging mistake (`add -A` instead of an explicit path) would sweep unrelated mirrored documents into every PR
docs_sync: required
docs_sync_reason: the mid-run edit semantics (the overlay is a snapshot taken at worktree creation/refresh) become a documented contract in the aet-work skill reference
---

# Plan: Sync the Live Plan into the Worktree and Seed It into the Task Branch

## Context

- PRD: `docs/prds/local-only-plans-prd.md` (R-3, R-5, R-7)
- ADR: `docs/adr/054-plan-documents-are-outside-the-durability-gate.md` —
  decisions 3 and 4 govern this plan: the plan travels with its PR, and
  correction (overlay + fail-closed resolution) replaces ADR-027's prevention.
- Depends on `lop-01`, which defines the deferred-path constant this plan
  consumes and makes untracked plans the normal case.

**Verified current behaviour (2026-08-05):**

- `copy_untracked_files` (`src/aet/worktree.py:255`) mirrors **untracked** files
  from six directories (`docs/plans/`, `docs/prds/`, `docs/adr/`,
  `docs/audits/`, `docs/retros/`, `docs/product-briefs/`) into the worktree.
  A plan that is *tracked but modified*, or *tracked but absent from the base*,
  is not copied — the worktree keeps the base's version or has none.
- The orchestrator switches to the worktree copy of the plan at
  `src/aet/cli/orchestrator.py:1257` and raises `MissingPlanError` at `:1260`
  when it is absent; the worktree copy is the operative document for every
  stage thereafter (`:1282`).
- `remove_worktree` (`src/aet/worktree.py:157-181`) removes a worktree only
  when `git rev-list --count <base>..HEAD` is `0`. Seeding a commit makes that
  count permanently ≥ 1, so without R-7 every worktree would leak.
- **Pre-existing inconsistency found at scope validation (2026-08-05):**
  `create_worktree`'s rebase-failure recovery calls
  `remove_worktree(repo_root, task_id)` at `worktree.py:76` **without** passing
  the `base_branch` it was given, so it silently falls back to the
  `origin/main` default. Under a non-trunk integration branch (ADR-045
  `single-pr`) the emptiness predicate is evaluated against the wrong ref.
  This is latent today; it stops being latent when R-7 rewrites that predicate,
  so the call site is fixed as part of task 3.
- Worktrees are created from `origin/<integration>`
  (`orchestrator.py:2438,2855`), so a plan carried only by an unpushed local
  commit is absent from the base — the case R-5's skip check guards.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
  — `copy_untracked_files` behaves as designed; this widens what it covers.

## Locked design

- **The overlay syncs by content, not by git state.** For paths in the deferred
  set the working-tree version is copied into the worktree unconditionally —
  untracked, modified, or absent from the base all resolve the same way. Git
  state stops being an input, which is what makes the agent's copy provably the
  latest local text.
- **The seeding commit stages one explicit path.** The worktree also holds
  untracked PRDs and ADRs mirrored by `copy_untracked_files`; a `git add -A` or
  `git commit -a` would sweep them into the PR. The commit stages the task's own
  plan file by path and nothing else. This is the single most likely way to get
  this plan wrong, so it carries a dedicated acceptance test with a decoy
  untracked plan and a decoy untracked PRD present.
- **Seeding is skipped when the base already carries the plan.** Checked with
  `git cat-file -e <integration>:<path>`. Without this, a plan carried by an
  unpushed local commit (permitted by `lop-01`'s R-4(b)) would be added
  independently on both branches and produce an add/add conflict at merge — in
  the unattended path, where nobody is watching.
- **Cleanup classifies paths, not commits.** `remove_worktree`'s emptiness test
  changes from "zero commits ahead" to "no changed path outside the deferred
  set", resolved with `git diff --name-only <base>..HEAD`. This subsumes the
  old zero-commit case rather than special-casing beside it, so a worktree with
  only a seeded plan commit is still "empty" and a worktree with any
  implementation commit is still retained.
- **A standalone plan commit, not folded into the first implementation commit.**
  It gives the PR a clean narrative and makes the cleanup diff trivially
  classifiable. (Confirmed at scope validation, 2026-08-05.)
- **The overlay is a snapshot.** Editing a plan in the main checkout mid-run
  does not propagate; the sync happens at worktree creation and refresh. This is
  intended and gets documented rather than engineered around.

## Rejected Alternatives

- **Extend `copy_untracked_files` in place to cover all six directories
  regardless of git state** — rejected: it would silently start overwriting
  worktree copies of tracked PRDs and ADRs with working-tree versions, which is
  a much wider behaviour change than this PRD scopes. The deferred set is
  `docs/plans/` only.
- **Rebase the worktree onto the local integration branch instead of copying**
  — rejected: contradicts the PRD's Non-Goal and ADR-044/045; the worktree base
  model is deliberately untouched.
- **Stage with `git add -A` and rely on `.gitignore`** — rejected: the mirrored
  PRDs and ADRs are legitimately un-ignored files; only an explicit path is safe.
- **Fold the plan into the first implementation commit** — rejected: it makes
  the cleanup classification depend on parsing a mixed diff, and muddies the PR.
- **Keep `remove_worktree`'s commit count and special-case `count == 1`** —
  rejected: it would retain any worktree whose seeded commit was followed by an
  empty implementation, and it encodes a magic number instead of the actual
  question ("did any real work land here?").

## Task List

1. Replace `copy_untracked_files`' untracked-only logic for deferred paths with
   a content sync that runs regardless of git state; leave the six-directory
   untracked mirror intact for the other five directories — M (traces: R-3)
2. Seed the task branch with a standalone commit adding only the task's own
   plan file by explicit path, skipped when
   `git cat-file -e <integration>:<path>` succeeds — M (traces: R-5)
3. Change `remove_worktree`'s emptiness test from a commit count to a
   changed-path classification over the deferred set, and pass the configured
   base at the `worktree.py:76` recovery call site so the predicate is
   evaluated against the right ref under a non-trunk integration branch — S
   (traces: R-7)
4. Tests: overlay covers untracked / modified / absent-from-base; the seeding
   commit contains exactly one file with a decoy plan and decoy PRD present;
   the skip path produces no duplicate commit and merges without conflict; a
   plan-only worktree is removed and an implementation worktree is retained
   (see Validation Steps) — M (traces: R-3, R-5, R-7)
5. Document the snapshot semantics of the overlay in the aet-work skill
   reference — S (traces: R-3)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: `lop-01` already delivers a working end-to-end path for
  untracked plans; this plan changes *where the plan lands* (the PR diff rather
  than a closure commit on the integration branch) and is independently
  reviewable and shippable on top of it.
- [x] Expected diff materially exceeds branch/PR overhead: three `worktree.py`
  functions, an orchestrator seeding step, and the leak-prevention suite.
- [x] Cannot share a branch with `lop-01`: R-7 exists only because R-5 creates
  a commit, and R-5's skip check depends on `lop-01`'s R-4(b) being live.

## Files to Modify

- `src/aet/worktree.py` (overlay, seeding helper, `remove_worktree`)
- `src/aet/cli/orchestrator.py` (invoke seeding after materialization)
- `tests/` — worktree overlay, seeding isolation, cleanup classification
- `skills/aet-work/` reference (overlay snapshot semantics)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-3, R-5, R-7 each covered by ≥ 1 task
- [ ] New source files: none introduced; new helpers live in `worktree.py` and
      are covered by `tests/` worktree coverage
- [ ] Unit: path classification and skip predicate. Integration: create worktree
      → overlay → seed → inspect branch contents. Boundary: real git repo with
      an unpushed local plan commit, asserting a conflict-free merge
- [ ] Leak test is mandatory and named: seeding commit contains exactly one
      file while a decoy untracked plan and decoy untracked PRD are present
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the branch. The overlay and the cleanup test are pure function changes;
the seeding step is additive. Task branches created while this was live carry
one extra plan commit, which is harmless after revert — the plan simply appears
in the PR diff. No data format or migration is involved.

## Pipeline

`standard` — the seeding commit touches git state inside the worktree and the
leak risk warrants a separate review pass over an isolated implementation stage.

---

*Stage: reviewed*
*Next step: run `aet-cso`*

---
id: t2r-03-ship-stacked-pr-split-trunk
size: M
work_class: normal
blocked_by:
  - t2r-02-ship-squash-verify-fallback
pipeline: standard
security_review: required
security_review_reason: rewrites git-mutation paths (reset --soft, rebase, push) in the ship surface
docs_sync: required
docs_sync_reason: deletes one skill example file and rewrites two aet-ship references
---

# Plan: `aet ship` Stacked-PR Completion, `aet ship split`, and Trunk Substitution

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-2, `aet ship`
remainder of prose-to-code study §3.1.3 —
`content/aet-structural-review/prose-to-code-study.md:105-111`).
Incident evidence: stacked PR S2-T2 landed in the wrong branch because
no signal surfaced after its parent merged (learnings:3, 2026-05-12).

This plan covers three of the five R-2 items; the close-side items
(squash-merge diff-match fallback `aet ship verify --squash-fallback`,
atomic record-then-delete `aet ship close --delete-branch`) belong to
**t2r-02-ship-squash-verify-fallback**, which merges first — both plans edit
`src/aet/cli/ship.py` heavily, so they are sequenced, never concurrent.

Current-state facts verified against the repo:

- `src/aet/cli/ship.py` hardcodes `origin/main` in `_determine_pr_base()`
  (`:219`), `_rebase_independent_branch()` (`:244`), `_build_pr_body()`
  (`:533-540`), the `cmd_merge` `--branch` default (`:1013`), and the
  Typer/argparse help texts — while `skills/aet-ship/SKILL.md:66-69`
  already claims commands resolve trunk themselves. The resolution
  machinery exists and is unused by ship.py: `src/aet/branch_ref.py`
  (`resolve_trunk_branch`: config `trunk_branch` →
  `git symbolic-ref refs/remotes/origin/HEAD` → `main`), already wired
  in `src/aet/cli/aet_state.py:38-51` via `resolve_config` on
  `.agents/aet-config.json`. This plan adopts that exact pattern.
- Stacked detection exists in first-pass form: `_determine_pr_base()`
  finds the nearest named ancestor and `_build_pr_body()` injects a
  "⚠️ STACKED PR" block. What is missing per §3.1.3: stack
  position/parent in the body, trunk-correct instructions, a fail-closed
  guard in `aet ship merge`, and the ledger fact.
- The monolithic-commit halt in `cmd_open`/`cmd_merge` (`:634-639`,
  `:874-879`) ends with "STOP and split the commit manually" — prose.
  `aet ship split` codifies the mechanics of
  `skills/aet-ship/references/commit-splitting.md:38-45`.
- Post-slc state (ADR-055): closure and footers are code-owned by
  `aet ship close` / `aet gate submit`; this plan adds no prose writer
  around either. Ledger taxonomy (`src/aet/ledger.py:28-29`) supports
  kinds `{cut, stage, verdict, land}` and ref kinds including `pr`
  (currently unused) — the stacked-PR-open fact fits `cut` + `pr`.

Collision notes:

- `skills/aet-ship/references/squash-merge-handling.md` is primarily
  t2r-02-ship-squash-verify-fallback territory (the diff-match algorithm becomes
  `--squash-fallback`). This plan touches only its line-3
  "substitute `<trunk>`" instruction; if t2r-02-ship-squash-verify-fallback deletes the file
  outright, that sub-item evaporates on rebase.
- `skills/aet-ship/references/ship-checklist.md` is flagged stale by
  study §3.1.6 — left to the R-9/R-10 docs plans, not touched here.
- mvr-01 (merged) removed `merge_verified`; no overlap with this scope.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Trunk substitution in `src/aet/cli/ship.py`: resolve trunk via
   `resolve_trunk_branch(repo_root, resolve_config(".agents/aet-config.json"))`
   (the `aet_state.py:38-44` pattern) and thread the resolved ref
   through `_determine_pr_base()`, `_rebase_independent_branch()`,
   `_build_pr_body()`, `_create_pr()`, the `cmd_merge` `--branch`
   default (argparse `:1013` and Typer `:1190-1194` — default becomes
   `None`, resolved at runtime), and all help/body strings that say
   "main". Delete the "substitute `<trunk>`" prose at
   `skills/aet-ship/references/squash-merge-handling.md:3` (if the file
   survives t2r-02-ship-squash-verify-fallback) — M (traces: R-2)
2. Stacked-PR completion in `aet ship open`: refactor
   `_determine_pr_base()` to return the stack (trunk ref, parent branch,
   position in chain) instead of a bare base string; `_build_pr_body()`
   injects a stack section naming the parent branch, the position
   (e.g. "PR 2 of 3"), and the post-parent-merge rebase instructions
   with the resolved trunk; the terminal stop-note uses the resolved
   trunk. Delete `skills/aet-ship/examples/stacked-branch-example.md`
   wholesale — detection, parent identification, body injection, and
   the stop-note are now code — M (traces: R-2)
3. Stacked merge guard in `cmd_merge`: when the detected stack parent
   differs from the resolved trunk and `--branch` targets the trunk,
   exit non-zero naming the parent ("merge into `<parent>` or rebase
   onto `<trunk>` first"); skipped when `--base` explicitly overrides
   detection — S (traces: R-2)
4. `aet ship split` subcommand (argparse + Typer wiring in
   `src/aet/cli/ship.py`): refuses on a dirty tree or empty PR range;
   prints the original HEAD SHA for recovery, runs
   `git reset --soft <pr_base>`, then commits caller-supplied groups
   (repeated `--message`/`--paths` pairs, in order); fail-closed
   post-condition — `git diff <orig HEAD> HEAD` must be empty, else exit
   non-zero with `git status` and the recovery command. Update the two
   `_is_monolithic_commit` halt messages to name `aet ship split`.
   Slim `skills/aet-ship/references/commit-splitting.md` to the
   bisectability judgment sections, pointing mechanics at the command;
   add the command to `skills/aet-ship/SKILL.md` Commands — M (traces: R-2)
5. Ledger fact on stacked PR open: after successful PR creation with a
   non-trunk base, emit `Ledger().write_event(source="aet-ship",
   task=<plan id>, kind="cut", ref=<PR URL>, ref_kind="pr",
   payload={"pr_base": ..., "stacked": True, "parent": ...})` —
   S (traces: R-2)
6. Tests: new `tests/test_ship_split.py` (unit + fixture-repo
   integration); extend `tests/test_ship_open.py` (stacked body
   injection + ledger event), `tests/test_ship_merge.py` (stacked merge
   guard), and `tests/test_ship_gate.py` (non-`main` trunk fixture) —
   M (traces: R-2)
7. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: the open/split/trunk surface is independently
  shippable and reviewable apart from t2r-02-ship-squash-verify-fallback's close-side machinery.
- [x] Expected diff (~500–550 lines across src, tests, and skill
  deletions) materially exceeds branch/PR/review overhead.
- [x] Cannot share a branch with t2r-02-ship-squash-verify-fallback: both edit
  `src/aet/cli/ship.py` and `squash-merge-handling.md`; one branch would
  entangle two R-2 slices and guarantee rebase conflicts — hence
  `blocked_by: t2r-02-ship-squash-verify-fallback` instead of a merge.

## Rejected Alternatives

- **Heuristic auto-split (group by file/directory without `--paths`)** —
  rejected: commit grouping is judgment, and the study's rule is
  mechanics to code, judgment to prose; a wrong automatic grouping is
  worse than the manual halt it replaces.
- **Interactive `git add -p` driver** — rejected: interactive staging
  cannot run in orchestrated/headless sessions, recreating the exact
  failure mode the codification exists to remove.
- **A new `aet trunk` resolution command or config refactor** —
  rejected: `src/aet/branch_ref.py` already resolves trunk with
  provenance and `aet_state.py` already wires it; ship.py adopts the
  same pattern, no new surface.
- **Fold into t2r-02-ship-squash-verify-fallback as one R-2 plan** — rejected: two heavy writers on
  `src/aet/cli/ship.py` in one branch is the rebase-conflict pattern;
  sequencing keeps each diff reviewable.
- **Delete `commit-splitting.md` entirely** — rejected: "what makes a
  commit bisectable" is judgment the study explicitly leaves in prose;
  only the reset/restage mechanics move to code.

## Files to Modify

- `src/aet/cli/ship.py`
- `skills/aet-ship/SKILL.md`
- `skills/aet-ship/references/commit-splitting.md`
- `skills/aet-ship/references/squash-merge-handling.md` (line-3 prose only; may be gone post-t2r-02-ship-squash-verify-fallback)
- `skills/aet-ship/examples/stacked-branch-example.md` (deleted)
- `tests/test_ship_split.py` (new)
- `tests/test_ship_open.py`
- `tests/test_ship_merge.py`
- `tests/test_ship_gate.py`

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`make test`)
- [ ] `tests/test_ship_split.py` (new): unit — dirty-tree and
  empty-range refusals, `--message`/`--paths` pairing errors;
  integration — fixture repo where split commits reproduce the
  original tree (`git diff <orig> HEAD` empty) and a deliberately
  incomplete grouping exits non-zero naming the recovery SHA
- [ ] `tests/test_ship_open.py` (extended): stacked fixture produces a
  PR body containing the parent branch, stack position, and resolved
  trunk; the `cut`/`pr` ledger event is written (integration)
- [ ] `tests/test_ship_merge.py` (extended): stacked branch targeting
  trunk exits non-zero naming the parent; targeting the parent passes
  (integration)
- [ ] `tests/test_ship_gate.py` (extended): fixture whose
  `refs/remotes/origin/HEAD` points at a non-`main` trunk — base
  detection and rebase target use it (integration)
- [ ] `grep -n "origin/main" src/aet/cli/ship.py` shows no hardcoded
  verification target outside the `branch_ref.py` fallback path, and
  `grep -rn "substitute" skills/aet-ship/` shows no trunk-substitution
  prose
- [ ] R-trace coverage: R-2 covered by tasks 1–6 (shared with t2r-02-ship-squash-verify-fallback,
  which owns the close-side remainder); no task cites another R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. Skill prose deletions restore with the revert; the
ledger event is an additive fact and remains valid. `aet ship split`
rewrites branch-local commit structure only — it prints the original
HEAD SHA before resetting, and `git reset --soft <orig SHA>` plus a
re-commit restores the prior state.

## Pipeline

`standard` — git-mutation paths (reset/rebase/push) change in the ship
surface; default grouping applies, no isolation override warranted.

---

*Stage: implemented*
*Next step: run `aet-qa`*

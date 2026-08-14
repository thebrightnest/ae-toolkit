---
id: sst-01-agents-path-registration
size: S
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
docs_sync: required
---

# Plan: Register Every File AET Writes Under `.agents/`, and Name the Halt

## Context

- PRD: `docs/prds/open-work-board-prd.md` (Phase 1, R-1/R-2/R-3)
- Audit: `reports/2026-08-12-prose-vs-enforcement-open-items.md`
- Audit items 3, 8, 13 (D4, D5 in `aet-toolkit-defects.md`)
- ADR-027 (main hygiene halts unattended), ADR-054 (deferred plan durability)

**Phase 1 — ships first and alone.** Projects bootstrapped by `aet setup` halt today: the
first AET command that records a ledger event leaves an untracked file that
`check_base_hygiene` refuses, and `git status --short --untracked-files=all`
means the file need not even be tracked. This plan must not wait on the transport
design in `sst-04`/`sst-05`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The one reproducible-defect item in the audit (the 2026-08-11 settled-tasks
      incident) is a PRD non-goal and routes to `aet-bug-report`

## Task List

1. **Split the two hygiene declarations.** `AET_IGNORED_PATHS` currently feeds both `write_aet_gitignore_entries()` (what `aet setup` puts in a project's `.gitignore`) and `check_base_hygiene()` (what the dirty check forgives), so a tracked-but-tool-written file cannot be expressed. Introduce a distinct tolerated-dirty declaration alongside `DEFERRED_PATH_PREFIXES` and point each consumer at the set it actually means — S (traces: R-2)
2. **Register `.agents/ledger.jsonl` and its lock as not-tracked**, so the gitignore writer emits them and the hygiene gate forgives them — S (traces: R-1)
3. **Register `.agents/learnings.jsonl` as tolerated-dirty, not ignored.** It is meant to be tracked and committed; `aet learnings append` (which `aet-evolve` requests on every retro) must not halt the next run — S (traces: R-1, R-2)
4. **Add the registration test.** Enumerate the toolkit's writers under `.agents/` and assert each target path appears in exactly one declaration. This is the half that stops the next store from repeating the omission — S (traces: R-1)
5. **Name the paths in the halt.** `check_base_hygiene` returns a bare `"Working tree is dirty"` while holding `dirty_lines`; print up to ten offending paths with a `(+N more)` suffix — S (traces: R-3)
6. Merge branch to main and verify integration — S

## Floor Check

- [x] This stands alone as an independently shippable behaviour change — it is
      the only item that unblocks downstream projects today.
- [x] The expected diff materially exceeds branch/PR/review overhead: two
      constants, two consumers, a new test module, one message.
- [x] It cannot share a branch with `sst-05`/`sst-06`, whose transport work would
      delay it behind an ADR.

## Rejected Alternatives

- **Adding the ledger to `AET_IGNORED_PATHS` alone** — rejected: it settles the
  ADR-055 question by default (declaring the ledger machine-local) while the PRD
  wires the opposite branch, and it cannot express `learnings.jsonl`.
- **Gitignoring `learnings.jsonl`** — rejected: the file is meant to be tracked
  and reviewed; ignoring it would silently stop learnings from being committed.
- **Waiting for `sst-06` to remove the in-tree ledger** — rejected: adopting
  projects halt now, and the transport is several plans away.

## Files to Modify

- `src/aet/worktree.py`
- `src/aet/cli/setup.py`
- `tests/worktree/` (new registration test module)
- `tests/installer/test_installer.py`

## Requirement Coverage

This plan covers Phase 1 of the PRD (R-1, R-2, R-3) and ships alone: downstream
projects halt today and must not wait on the rest of the programme. R-4 through
R-23 are covered by the `owb-*` plan set (11 plans after guardrail review).

## Validation Steps

- [x] `aet learnings append` followed by `check_base_hygiene` reports a clean tree
- [x] `.agents/learnings.jsonl` is still tracked after the change
- [x] A deliberately unregistered writer makes the new test fail
- [x] A dirty tree with three stray files names all three in the halt message
- [x] Lint passes
- [x] Tests pass
- [x] R-trace coverage: every in-scope R-id is covered by a task above
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Both declarations are pure data read at call time; no state is migrated and no file on disk changes shape.

---

_Stage: qa-complete_
_Next step: run `aet-review`_

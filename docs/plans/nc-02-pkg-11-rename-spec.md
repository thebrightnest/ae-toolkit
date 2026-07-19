---
id: nc-02-pkg-11-rename-spec
size: S
blocked_by:
  - nc-01-namespace-taxonomy-adr
pipeline: minimal
status: queued
security_review: skipped
security_review_reason: This ticket only edits pkg-11's plan-document content (task list, context, files-to-modify); no code lands here. pkg-11's own security_review already covers the eventual rename implementation.
docs_sync: skipped
docs_sync_reason: This ticket edits a plan file, not shipped docs; the actual doc sync for the renames is already gated by pkg-11's own docs_sync (required).
---

# Plan: Amend pkg-11 with the CLI Rename Spec

## Context

Source: `docs/prds/namespace-consolidation-prd.md`, R-2. Target: `docs/plans/pkg-11-typer-consolidation.md` — already `status: queued`, `blocked_by: pkg-06-cross-skill-extraction`, footer `plan-approved`, sourced from a *different* PRD (`docs/prds/aet-package-extraction-prd.md`, its own R-8). Its existing task 2 is explicitly scoped as behavior-preserving ("preserving flags, defaults, and help text") — the rename must land as a new, separate task, not folded into task 2's wording, and must cite this PRD's R-1/R-2, not pkg-11's existing R-8, to avoid R-id collision within the same file.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] N/A — no defect redirect needed

## Task List

1. Read `docs/adr/039-namespace-taxonomy.md` (produced by `nc-01`) and extract the settled new names for `review`, `plan`, and `sync` — S (traces: R-1, R-2)
2. In pkg-11's Context section, add a citation to ADR-039 as the naming source of truth for this plan's rename work — S (traces: R-2)
3. Insert a new task immediately after pkg-11's existing task 2 implementing the actual renames for `review`/`plan`/`sync` per ADR-039: retire each old subcommand name in the same merge that ships its replacement (no alias), extend `scripts/skills-lint` to validate the new shape, sweep canonical docs (`AGENTS.md`, `docs/CONVENTIONS.md`, live `SKILL.md` invocation examples) and live skills for the old names, and add a grep-guard regression test — the exact transition vehicle gib-06 already proved. Renumber pkg-11's subsequent tasks accordingly — M (traces: R-1, R-2)
4. Update pkg-11's `docs_sync_reason` to name the rename explicitly, rather than the current generic "re-validated against the new parser tree" — S (traces: R-2)
5. Update pkg-11's "Files to Modify" list: drop the "(if invocation examples change)" qualifier on `docs/CONVENTIONS.md` (it now unconditionally changes) and add any `SKILL.md` files whose invocation examples reference `aet review`, `aet plan`, or `aet sync` — S (traces: R-2)
6. Update pkg-11's "Validation Steps" to add: old names (`review`, `plan`, `sync`) are absent from `aet --help` and from every canonical doc post-merge; `skills-lint` fails on a deliberately reintroduced old-name invocation — S (traces: R-2)
7. Audit every other Phase A1 plan (pkg-01 through pkg-10, pkg-12 onward) to confirm none performs a rename; record the confirmation in this ticket's notes rather than editing those plans — S (traces: R-2)
8. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [x] The diff is expected to exceed 3 files or 50 lines (pkg-11 is edited in several distinct sections plus an audit note).
- [x] The work cannot share a branch/PR with related tasks — it carries its own `blocked_by` edge (`nc-01`) independent of pkg-11's existing one (`pkg-06`).

## Rejected Alternatives

- **Renaming directly against pkg-11 without a separate tracked ticket** — rejected: R-2 frames this as its own amendment so it can carry a `blocked_by: nc-01` edge independent of pkg-11's existing `blocked_by: pkg-06`; folding it silently into pkg-11 would hide that dependency from the queue's DAG.
- **Leaving the rename scope undefined until pkg-11's own implementation time** — rejected: pkg-11 is already `plan-approved`; deferring the rename decision to execution would re-open an approved plan's scope mid-implementation, which the pipeline treats as a locked-in-architecture violation.

## Files to Modify

- `docs/plans/pkg-11-typer-consolidation.md`

## Validation Steps

- [ ] Lint passes
- [ ] R-trace coverage: R-2 covered by tasks 2–7; task 1 reads R-1's output but adds no new R-1 obligation; no task cites an unknown R-id
- [ ] Named check per new file: N/A — no new file is introduced; pkg-11 is amended in place. Confirm the amended pkg-11 still passes its own self-consistency checks (files-assigned-to-tasks, R-trace coverage) after the edit
- [ ] Test types: N/A — plan-document edit only, no executable code
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit amending pkg-11; pkg-11 reverts to its pre-amendment state (Typer migration only, no renames), which was already a valid, independently mergeable plan.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | ---------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

`minimal` fits here: a contained plan-document edit with no code, dependency, auth, or API surface of its own.

---

*Stage: plan-approved*
*Next step: run `aet-work`*

---
id: nc-01-namespace-taxonomy-adr
size: M
blocked_by: []
pipeline: minimal
status: queued
security_review: skipped
security_review_reason: Docs-only ADR; no code, dependency, or config surface changes.
docs_sync: required
docs_sync_reason: AGENTS.md's Decision Log needs a new bullet pointing at ADR-039, matching the existing ADR-036/037/038 pattern.
---

# Plan: Namespace Taxonomy ADR

## Context

Source: `docs/prds/namespace-consolidation-prd.md`, R-1. Precedents: `docs/adr/007-ship-release-prep-separation.md` (the boundary R-3 completes, not redraws), `docs/plans/gib-06-command-groups-sprint-add.md` (noun-scoped, nested-verb convention and the atomic/alias-free rename mechanism, both already proven live), and ADR-036/037/038 (this repo's existing ADR + Decision Log pattern to follow).

This ticket is a decision-making act, not a mechanical edit — the actual new names for `review`/`plan`/`sync` are chosen when this ticket is *implemented*, not at planning time. `nc-02-pkg-11-rename-spec` and `nc-03c-ship-unify-retire-legacy` both `blocked_by` this ticket because they consume its output (the settled names and the ship/evolve dispositions).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] N/A — no defect redirect needed

## Task List

1. Draft `docs/adr/039-namespace-taxonomy.md` using `docs/adr/000-template.md`'s structure (Status / Context / Decision / Consequences / Alternatives Considered) — M (traces: R-1)
2. In the Decision section, record the separation principle verbatim: deterministic work → code/CLI, judgment → skill, and after separation no two things share a name — S (traces: R-1)
3. Record the per-side naming convention: noun-scoped, nested-verb, inheriting the pattern gib-06 already established (`aet state <sub>`, `aet sprint add`). Explicitly reject flat hyphenation (e.g. `aet queue-sync`) and a bare noun with no verb (e.g. `aet board`) as repeating the shape gib-06 already rejected for `add` — S (traces: R-1)
4. Settle a full five-row collision table, one row per collision identified in the 2026-07-19 audit:
   - **ship** — record R-3's already-decided disposition: the bare `ship` binary is retired; `aet ship` is already correctly named (no rename). Note explicitly that the SKILL.md residue-vs-retirement question is `nc-03c`'s own call, not this ADR's — this row only records the naming disposition.
   - **evolve** — record that the code half already exists correctly (`aet retro`, `aet mine-learnings`); `aet-evolve` stays skill-only. Decide whether `aet evolve` gets a friendly stub error (e.g. "this is a skill — activate it, or see `aet retro`") or stays absent from the CLI namespace.
   - **review** — choose a new name for the CLI subcommand `aet review` (colliding with the judgment-only skill `aet-review`), evaluated against the candidate `aet gate review` or an equivalent noun-scoped, nested-verb form.
   - **plan** — choose a new name for the CLI subcommand `aet plan` (colliding with the skill `aet-plan`), evaluated against the candidate `aet plan validate` or an equivalent form.
   - **sync** — choose a new name for the CLI subcommand `aet sync` (colliding with `aet-sync-docs`), evaluated against the candidate `aet queue sync` or an equivalent form.
   — M (traces: R-1)
5. Specify every review/plan/sync rename as atomic and alias-free by default: the old subcommand name is retired in the same merge that ships the new one, using the exact transition vehicle gib-06 already proved — extend skills-lint to validate the new shape, sweep canonical docs + live skills, add a grep-guard regression test. Name this mechanism explicitly so `nc-02` inherits it rather than re-deriving it — S (traces: R-1)
6. Record rejected alternatives inside the ADR's own "Alternatives Considered" section: shims/aliases, an incremental deprecation window, flat hyphenation, bare-noun-no-verb — each with the reason it was rejected — S (traces: R-1)
7. Restate the full 2026-07-19 command-surface inventory (20 skills, 23 CLI subcommands, ~25 bin executables) in the ADR's Context section as the durable evidence base, rather than leaving it in session discussion — S (traces: R-1)
8. Add a bullet to `AGENTS.md`'s Decision Log (§Decision Log, after the ADR-038 bullet) summarizing the settled taxonomy and pointing to ADR-039, matching the existing bullet format ("**Label:** one-line summary. See ADR-NNN.") — S (traces: R-1)
9. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

If a task exceeds the agent session limit (≤ 4 hr / ≤ 8 files / ≤ 300 lines), split it into subtasks and document the relationship with `Split from: {parent-task-id}`.

### Batching Check

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks — it must merge before `nc-02`/`nc-03c` can start, since both are `blocked_by` it.

## Rejected Alternatives

- **Deciding the new names now, during planning, instead of deferring to this ticket's own implementation** — rejected: naming is the actual content this ticket produces; deciding it at plan-authoring time would quietly bypass the standard draft→queued→run→merged pipeline for what is a real, reviewable decision.
- **Bundling ADR-writing with `nc-02` (the pkg-11 rename-task amendment) into one ticket** — rejected: they are separable deliverables with different downstream consumers (`nc-03c` depends only on the ADR, not on `nc-02`); merging them would force an inaccurate DAG edge.
- **Skipping a taxonomy ADR and picking names ad hoc in each downstream ticket** — rejected: this is exactly the documentation-drift failure mode the PRD's own Overview describes; a single settled reference prevents `nc-02` and `nc-03c` from disagreeing on names.

## Files to Modify

- `docs/adr/039-namespace-taxonomy.md` (new)
- `AGENTS.md`

## Validation Steps

- [ ] Lint passes (`make lint` — markdownlint on the new ADR file)
- [ ] R-trace coverage: R-1 is fully covered by tasks 1–8; no task cites an R-id outside R-1's scope
- [ ] Named check per new file: `docs/adr/039-namespace-taxonomy.md` is covered by `scripts/validate-skills.sh`'s relative-link validation and by `make lint`; no unit/integration test applies since this plan produces no executable code
- [ ] Test types: N/A — documentation only; no unit, integration, or API-boundary code is introduced
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the ADR commit; `AGENTS.md`'s Decision Log bullet reverts with it. No code or renames land in this ticket, so rollback has zero blast radius on any running system — it only un-publishes a decision document. Any downstream ticket that already started implementation against the ADR's settled names (`nc-02`, `nc-03c`) would need to pause until the ADR is restored or superseded.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | ---------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

`minimal` fits here: this is a docs-only decision record with no dependency, auth, data, or API surface — the kind of low-risk work `pipeline: minimal` is for (matches `pkg-01-decision-records`, the same-shaped ADR-writing ticket already merged in this repo).

---

*Stage: plan-approved*
*Next step: run `aet-work`*

---
id: nc-03b-ship-pr-creation-as-code
size: M
blocked_by:
  - nc-03a-ship-gate-as-code
pipeline: standard
status: queued
security_review: required
security_review_reason: New code pushes branches and opens PRs via gh; behavior-review relevant (force-with-lease usage, PR body construction) even without a new dependency.
docs_sync: required
docs_sync_reason: aet-ship/SKILL.md steps 10-13 move to code and must be trimmed to a pointer.
---

# Plan: Promote aet-ship's PR Creation to Code

## Context

Source: `docs/prds/namespace-consolidation-prd.md`, R-3. `Split from: nc-03 (aet ship consolidation)`, sibling of `nc-03a` (gate) and `nc-03c` (unify + retire legacy). This ticket promotes `aet-ship/SKILL.md` steps 10-13 (bisectable-commit check, CHANGELOG generation, push, PR creation) to a new `aet ship open` subcommand. `blocked_by: nc-03a` because PR creation must refuse to proceed if the gate fails — it consumes `nc-03a`'s gate result and scope-audit text directly.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] N/A — no defect redirect needed

## Task List

1. Add an `aet ship open` subcommand to `src/aet/cli/ship.py`, scaffolding `tests/test_ship_open.py` alongside it; it invokes `aet ship gate`'s logic first and refuses to proceed (non-zero exit, no push) if the gate reports failure — M (traces: R-3)
2. Port the bisectable-commit **check** (step 10) as a deterministic flag, not an automated split: if the diff looks monolithic (e.g. a single commit spans the entire `pr_base..HEAD` range while the plan lists more than one task), **STOP** and ask the agent to split manually. The judgment of *how* to split a commit into logical pieces stays out of code, consistent with the deterministic/judgment separation this workstream is built on — M (traces: R-3)
3. Port CHANGELOG **entry** generation (step 11: derived from commit messages and the plan.md summary) as PR/commit-trail output only — it must **not** write the project-level `CHANGELOG.md` file, which remains `aet-release-prep`'s domain (ADR-007; aet-ship SKILL.md line 18 already states ship "does not update project-level `CHANGELOG.md`"). This completes ADR-007's boundary, it does not redraw it — S (traces: R-3)
4. Port push logic (step 12: `git push --force-with-lease` if the branch was rebased by `aet ship gate`, else a normal `git push`) — S (traces: R-3)
5. Port PR creation (step 13: `gh pr create` against the gate-computed `pr_base`; body includes plan/PRD links, the scope-audit section from `nc-03a`'s output when non-empty, and the stacked-PR warning block when `pr_base` is not `origin/main`) — M (traces: R-3)
6. Preserve the existing guardrail verbatim: do not commit `chore(release)` or VERSION changes on feature branches (this ticket's code must not touch release versioning) — S (traces: R-3)
7. Trim `aet-ship/SKILL.md` steps 10-13, replacing them with a pointer: "see `aet ship open` (code)" — S (traces: R-3)
8. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions.
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with `nc-03a`/`nc-03c` — it has its own dependency edge and reviewable surface.

## Rejected Alternatives

- **Automating the commit split itself, not just the check** — rejected: deciding what constitutes "one logical change" within a messy diff is a judgment call, not a mechanical one; automating it risks silently producing a worse split than the agent would choose. Keep the check in code, the action in the agent.
- **Folding this into `nc-03a`** — rejected: the gate (read-only checks) and PR creation (mutating: pushes, opens a PR) are different risk classes and different reviewable units; `nc-03a` is already large enough on its own.
- **Porting step 11 as a write to the project `CHANGELOG.md`** — rejected: aet-ship's own SKILL.md (line 18) and ADR-007 both put project-level `CHANGELOG.md`/`PRODUCT.md` under `aet-release-prep`, not ship. Step 11's "CHANGELOG entry" is a mechanical, commit-derived PR/commit-trail artifact; porting it as a `CHANGELOG.md` file write would redraw the ADR-007 boundary R-3 explicitly says it only completes.

## Files to Modify

- `src/aet/cli/ship.py`
- `aet-ship/SKILL.md`
- `tests/test_ship_open.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-3 (PR-creation portion) covered by tasks 1–7; no unknown R-ids cited
- [ ] Named tests per new file: `tests/test_ship_open.py` covers `aet ship open` — gate-failure-refusal, monolithic-commit-stop, changelog-generation, force-with-lease-vs-normal-push branching, PR-body construction (scope-audit section present/absent, stacked-PR warning present/absent)
- [ ] Test types: unit tests (changelog generation, PR-body construction, in isolation); integration test (full open run against a scratch git repo + mocked `gh` CLI)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge. `aet-ship/SKILL.md` reverts to describing steps 10-13 as agent-executed prose. `nc-03c` (which wires `open` into the unified entry point) should not be implemented ahead of this revert landing cleanly.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | ---------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

`standard`: pushes branches and opens PRs — real side effects on shared state, warranting the default grouping.

---

*Stage: plan-approved*
*Next step: run `aet-work`*

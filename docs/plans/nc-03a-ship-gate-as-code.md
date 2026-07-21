---
id: nc-03a-ship-gate-as-code
size: L
blocked_by:
  - pkg-06-cross-skill-extraction
pipeline: standard
status: queued
security_review: required
security_review_reason: New code runs git/gh operations (fetch, rebase, diff, evidence-file reads) and gates merge readiness; behavior-review relevant even without a new dependency.
docs_sync: required
docs_sync_reason: aet-ship/SKILL.md steps 1-9 move to code and must be trimmed to a pointer; SKILL.md invocation examples change.
---

# Plan: Promote the aet-ship Pre-Merge Gate to Code

## Context

Source: `docs/prds/namespace-consolidation-prd.md`, R-3. `Split from: nc-03 (aet ship consolidation)` — R-3's real scope is the entire `aet-ship/SKILL.md` procedure (steps 1-15), not only the ship/bare-`ship` binary collision. Verified directly against `aet-ship/bin/ship` and `aet-ship/SKILL.md`: the existing `ship` script only implements step 14 (post-merge closure, via `aet-state`'s `record-merge`); steps 1-13 and 15 are deterministic prose the agent currently executes by hand. This ticket promotes steps 1-9 (everything through the scope audit) to code as a new `aet ship gate` subcommand. `nc-03b` (PR-creation-as-code) and `nc-03c` (unify entry point, retire legacy `ship`) are siblings — `Split from: nc-03` — and depend on this ticket.

`blocked_by: pkg-06-cross-skill-extraction` because pkg-06 relocates `aet-ship/bin/ship` → `src/aet/cli/ship.py` (task 1); writing this substantial new module makes sense once at its final package location, not once in the pre-move skill location and again after pkg-06 relocates it.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] N/A — no defect redirect needed

## Task List

1. Add an `aet ship gate` subcommand in `src/aet/cli/ship.py` (plain argparse subparser, matching the current pre-Typer convention every other `src/aet/cli/*.py` module uses — pkg-11's later Typer migration sweeps this up like every other file, no special handling needed here), scaffolding `tests/test_ship_gate.py` alongside it — M (traces: R-3)
2. Port fetch + PR-base computation and conditional rebase (SKILL.md steps 1-2: `git fetch origin`; merge-base/stacked-branch detection; rebase independent branches onto `origin/main`, **STOP** on conflict) to code — M (traces: R-3)
3. Port the clean-working-tree check (step 3: `git status --short`; stop and prompt stash/commit/abort on dirty tree) — S (traces: R-3)
4. Port test-suite invocation and coverage audit (steps 4-5) with structured pass/fail and coverage-delta reporting — M (traces: R-3)
5. Port the plan-completion check (step 6: verify every task in `docs/plans/{ticket}-plan.md` is addressed) — S (traces: R-3)
6. Port the stage-aware review/CSO-skip logic (step 7: read the plan footer `*Stage:*`; skip `aet-review`/`aet-cso` per the documented rule; print the existing `⏭️ Skipping {skill}: plan stage is already {stage}.` message) — M (traces: R-3)
7. Port the critical-class `aet-verify` evidence gate (step 8: check `.agents/verify/{ticket}-evidence.md` or `.agents/verify/{ticket}-evidence/` for mode/command/output/timestamp/signature; **STOP** with the existing message if absent) — S (traces: R-3)
8. Port the scope audit (step 9: `git diff "$pr_base" --name-only`; flag out-of-scope `docs/plans/*.md`/`docs/prds/*.md`; build the `## Scope audit` PR-body section text as structured output for `nc-03b` to consume) — S (traces: R-3)
9. Trim `aet-ship/SKILL.md` steps 1-9, replacing them with a pointer: "see `aet ship gate` (code)" — S (traces: R-3)
10. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

> **⚠️ ATOMIC OVERSIZED — requires explicit user approval.**
> Eight distinct checks (rebase, clean-tree, tests, coverage, plan-completion,
> stage-skip, critical-verify, scope-audit) all feed one gate result and one
> exit code — this is one user-visible behavior ("can this ship?"), not eight.
> Splitting further would cut across a single behavior boundary (horizontal,
> check-by-check) rather than a real vertical slice, and would leave an
> interim state where the gate partially runs as code and partially still
> requires the agent to read SKILL.md prose mid-check — worse than one larger
> reviewable diff. The three-way split at the `nc-03` parent level (gate / PR
> / unify) is the genuine vertical cut; this ticket is its own atomic unit.

### Batching Check

- [x] This is not one of several near-identical additions.
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with `nc-03b`/`nc-03c` — each has its own dependency edge and reviewable surface.

## Rejected Alternatives

- **Splitting further into one ticket per check (rebase, clean-tree, tests, ...)** — rejected: these eight checks share one result structure and one exit code; they are not independently user-visible behaviors, so splitting them would be layer-splitting, not vertical slicing.
- **Implementing this against the pre-pkg-06 location (`aet-ship/bin/ship`)** — rejected: pkg-06 relocates the file to `src/aet/cli/ship.py` shortly after; writing ~200+ new lines twice (once pre-move, once post-move) is wasted work for no benefit, hence `blocked_by: pkg-06-cross-skill-extraction`.
- **Writing this directly in Typer instead of matching the current argparse convention** — rejected: pkg-11 (blocked_by pkg-06, not yet implemented) is the ticket that migrates every `src/aet/cli/*.py` file to Typer in one pass; writing Typer here would pre-empt and fragment that migration.

## Files to Modify

- `src/aet/cli/ship.py` (post-pkg-06 location; `aet-ship/bin/ship` if implemented before pkg-06 lands, though `blocked_by` is intended to prevent that ordering)
- `aet-ship/SKILL.md`
- `tests/test_ship_gate.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-3 (gate portion) covered by tasks 1–9; no unknown R-ids cited
- [ ] Named tests per new file: `tests/test_ship_gate.py` covers `aet ship gate` — one test per ported check (rebase-conflict-stop, dirty-tree-stop, test-failure-stop, coverage-drop-flag, incomplete-plan-flag, stage-skip-logic for each of `synced`/`reviewed`/`qa-complete`, missing-evidence-stop for critical-class, scope-audit-flag) plus one happy-path all-checks-pass test
- [ ] Test types: unit tests (each check in isolation, git/gh calls mocked); integration test (full gate run against a scratch git repo fixture)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge. `aet-ship/SKILL.md` reverts to describing steps 1-9 as agent-executed prose; no other code depends on `aet ship gate` yet since `nc-03b`/`nc-03c` (which consume it) haven't landed at the point this would need reverting.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | ---------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

`standard`: real code with git/gh side effects and a merge-readiness gate — not auth or data-model, but risk-bearing enough to warrant the default grouping rather than `minimal`.

---

*Stage: reviewed*

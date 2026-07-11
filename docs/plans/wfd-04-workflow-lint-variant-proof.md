---
id: wfd-04-workflow-lint-variant-proof
size: M
blocked_by:
  - wfd-03-engine-rewiring
pipeline: standard
status: approved
security_review: skipped
security_review_reason: additive CI lint and test fixtures only — no auth, data-model, API, or dependency surface; gate sequencing untouched
docs_sync: required
docs_sync_reason: adds a make validate step and the variant contract worth documenting
---

# Plan: Workflow Lint in CI and the Team-Variant Exit-Gate Proof

## Context

- PRD: `docs/prds/roadmap-p1-workflow-as-data-prd.md` (G4; R-9, R-11, closing R-10)
- Two halves of the same guarantee: the lint makes a bad workflow file unmergeable (this repo's CI is `make validate`), and the variant test proves the good ones are actually flexible — the roadmap's exit gate: _a plausible second team's flow — different gates, different evidence, different routing — is expressible by editing only the file, with zero engine changes._
- The loader (workflow.py) tolerates unknown extension keys at runtime; the **lint** is the stricter merge-time judge. Both consume the same validation core so they cannot drift.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `aet-work/bin/validate-workflows` (new, stdlib-only CLI): validates the packaged `aet-work/workflows/*.json` and, when present, `<repo>/.agents/workflows/*.json`. Reuses `workflow.py`'s validation core, then adds merge-time-only checks: every bound skill resolves to a `<repo>/<skill>/SKILL.md` directory; every non-null `evidence` is a key of `evidence.SCHEMAS`; `session_groups` partition exactly the skilled stages; `routing` shape valid (`default` requires `harness`); duplicate stage names, empty stage lists, and unsupported `version` fail. Output: one line per finding, exit 1 on any failure, exit 0 with a summary line when green.
- `Makefile` `validate` target gains `./aet-work/bin/validate-workflows` after the pytest step.
- Team-variant fixture (`tests/fixtures/workflows/content.json`, loaded from a tmp repo's `.agents/workflows/`): a plausible content-team flow — stages `draft → edited → fact-checked → published` binding a different skill set, `evidence` only on `fact-checked` (reusing the `review` kind: variants rebind the fixed menu, never invent kinds), `gate_key` on `fact-checked` (`fact_check: required|skipped`), two session groups, `routing.by_stage` sending one stage to a hypothetical second harness. Fixture skills resolve via stub skill directories created by the test fixture.
- `tests/test_workflow_variant.py`: (a) the variant loads and lints clean; (b) `session_groups(isolation)` reflects the variant's groups; (c) orchestrator traversal with patched `run_stage`/`run_stage_group` walks the variant's stages end to end, honoring its `gate_key` via plan frontmatter — asserting no engine module was modified is structural: the test imports only public engine APIs and fixture data.
- `tests/test_workflow_lint.py`: one failing fixture per lint rule + green on the packaged default.

## Rejected Alternatives

- Ship the content workflow as a real packaged class — rejected: the second class waits for its Phase 8 trigger; here it exists only as proof of flexibility.
- Lint inside the loader (fail hard on unknown keys at runtime) — rejected: runtime tolerance + merge-time strictness lets extension axes land without engine releases while still gating what merges.
- New verdict kinds for the variant — rejected: evidence kinds are kernel (schemas + storage); variants rebind the fixed menu. Recorded as the honest limit of "flexibility by data."

## Task List

1. Write `aet-work/bin/validate-workflows` reusing the `workflow.py` validation core plus merge-time checks (skill resolution, evidence menu, group partition, routing shape) — M (traces: R-9)
2. Wire it into `Makefile` `validate` — S (traces: R-9)
3. Write `tests/test_workflow_lint.py`: per-rule failing fixtures + packaged default green — M (traces: R-9)
4. Write `tests/fixtures/workflows/content.json` and `tests/test_workflow_variant.py`: load, lint, group, and traverse the variant with zero engine changes — M (traces: R-10, R-11)
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition — the lint and the proof are one contract, batched here deliberately; splitting them would gate the exit criteria across two reviews
- [x] Diff expected > 3 files / > 50 lines
- [x] Cannot share a branch with the rewiring task it verifies

## Files to Modify

- `aet-work/bin/validate-workflows` (new)
- `Makefile`
- `tests/test_workflow_lint.py` (new)
- `tests/fixtures/workflows/content.json` (new)
- `tests/test_workflow_variant.py` (new)

## Validation Steps

- [ ] `make validate` passes — and now includes the workflow lint itself
- [ ] Named tests per new source file: `aet-work/bin/validate-workflows` → `tests/test_workflow_lint.py` (unit: every failure rule; integration: packaged default green); `tests/fixtures/workflows/content.json` → `tests/test_workflow_variant.py` (integration: load/lint/group/traverse)
- [ ] Deliberately breaking `aet-work/workflows/software.json` (unknown evidence kind) makes `make validate` exit non-zero; restoring it goes green
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; remove the Makefile line if reverted manually. Lint and fixtures are additive — no engine behavior changes to unwind.

---

_Stage: qa-complete_
_Next step: run `aet-review`_

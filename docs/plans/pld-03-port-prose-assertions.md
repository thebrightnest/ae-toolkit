---
id: pld-03-port-prose-assertions
size: M
blocked_by:
  - pld-02-docs-lint-engine
pipeline: standard
status: merged
security_review: skipped
security_review_reason: Relocation of existing documentation assertions into the rules file; no runtime, dependency, or execution-path changes beyond the already-reviewed pld-02 engine.
docs_sync: skipped
docs_sync_reason: The validate-gate description and command table were updated by pld-02; this plan moves assertion content only.
---

# Plan: Port Prose Assertions to Rules

## Context

PRD: `docs/prds/prose-lint-decoupling-prd.md` (R-4).
Decision: ADR-040, delivered by pld-01.
Engine: pld-02.

Four test modules assert against the repo's own Markdown. Each assertion is one
of the four patterns the rule grammar covers:

| Module | Asserts |
| --- | --- |
| `tests/skills/test_aet_qa.py` | required phrases in `aet-qa/SKILL.md` |
| `tests/skills/test_aet_review.py` | required phrases in `aet-review/SKILL.md` |
| `tests/ship/test_merge_governance.py` | section-scoped presence in `docs/CONVENTIONS.md`, ADR-029, and absence of self-merge directives in `aet-ship/SKILL.md` |
| `tests/test_scripts_layout.py` | `scripts/` layout plus content of `scripts/archive/README.md` |

This is a **relocation**. Every invariant ports 1:1; changing or dropping one
is out of scope and must be raised separately.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. [x] Port `test_aet_qa.py` and `test_aet_review.py` assertions into
   `.agents/doc-rules.yaml` as `must_contain` rules with reasons carried over
   from the existing assertion messages — S (traces: R-4)
2. [x] Port `test_merge_governance.py`, including the section-scoped rules against
   `docs/CONVENTIONS.md` and the `must_not_contain` rules that keep
   `aet-ship/SKILL.md` free of self-merge directives — M (traces: R-4)
3. [x] Port `test_scripts_layout.py`: layout checks as `path_exists` /
   `path_absent`, README content as `must_contain` — S (traces: R-4)
4. [x] For each ported invariant, break the underlying prose and confirm
   `aet docs lint` fails; restore. A port is not complete without this
   demonstration — M (traces: R-4)
5. [x] Delete the four test modules and confirm no module under `tests/` still
   reads Markdown from the checkout outside `tests/` — S (traces: R-4)
6. [x] Remove the four modules from `change_scope.DOC_COUPLED_TESTS`, leaving only
   the corpus module until pld-04 lands — S (traces: R-4)
7. [ ] Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions.
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks.

## Rejected Alternatives

- **Delete the tests and trust the rules without demonstration** — rejected: a
  silently non-firing rule is worse than the assertion it replaced, because it
  reads as coverage. Task 4 exists to prove each rule fires.
- **Improve or consolidate invariants while porting** — rejected: mixing
  relocation with re-litigation makes the diff unreviewable and risks dropping
  a governance check under cover of a refactor.
- **Leave `test_scripts_layout.py` in pytest** — rejected: its README content
  assertion is exactly the coupling this workstream removes, and its layout
  checks fit `path_exists` / `path_absent` cleanly.

## Files to Modify

- `.agents/doc-rules.yaml`
- `tests/skills/test_aet_qa.py` (deleted)
- `tests/skills/test_aet_review.py` (deleted)
- `tests/ship/test_merge_governance.py` (deleted)
- `tests/test_scripts_layout.py` (deleted)
- `src/aet/change_scope.py`

## Validation Steps

- [x] Lint passes
- [x] Tests pass
- [x] R-trace coverage: R-4 covered by tasks 1–6
- [x] No new source files introduced; rule coverage is demonstrated by task 4
- [x] Test types: the rules file replaces unit-level content assertions; the
      break-and-confirm pass in task 4 is the integration check
- [x] Every assertion in the four deleted modules maps to a rule, verified by
      count and by reading the diff side by side
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit; the deleted test modules return and the rules become
inert. Because pld-05 has not yet simplified `change_scope`, the fast path
still consults `DOC_COUPLED_TESTS` and remains correct either way.

## Pipeline

`standard` — deletes live governance coverage and must be reviewed carefully.

---

*Stage: merged*
*Next step: run `aet-ship`*

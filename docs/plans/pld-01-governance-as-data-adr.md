---
id: pld-01-governance-as-data-adr
size: S
blocked_by: []
pipeline: minimal
status: queued
security_review: skipped
security_review_reason: Decision record only; no code, runtime, or dependency changes.
docs_sync: required
docs_sync_reason: New ADR must be indexed in docs/adr/README.md and referenced from the validate-gate description in AGENTS.md.
---

# Plan: ADR — Documentation Invariants Are Data

## Context

PRD: `docs/prds/prose-lint-decoupling-prd.md` (R-1).

`make validate` is the only safety net in this repo — CI is ruled out on cost —
so it must be both complete and fast. The prose-only fast path achieves the
speed by enumerating the test modules that read repo Markdown, policed by an
AST guard. That enumeration exists only because documentation invariants are
written as pytest assertions. This ADR records the principle that replaces
them, before any engine is built against it.

The decision must also draw a boundary against `scripts/skills-lint`, which
already lints Markdown against code reality (validating documented `aet`
invocations against `SUBCOMMANDS` and each target's `build_parser()`). That
script keeps its single job; governance rules do not move into it.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Write ADR-040 (`040-documentation-invariants-as-data.md`) recording the
   principle — documentation invariants are declared as data and enforced by a
   lint stage, never asserted in the unit-test suite — the four-pattern rule
   grammar (`must_contain`, `must_not_contain`, section-scoped variants, path
   assertions), and the `skills-lint` boundary — S (traces: R-1)
2. Record the rejected alternatives that this workstream already considered so
   they do not silently re-open: extending `skills-lint`, keeping the checks as
   Python in a standalone script, and marker-based pytest selection — S
   (traces: R-1)
3. Index the ADR in `docs/adr/README.md` — S (traces: R-1)
4. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions.
- [ ] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks.

The ADR lands before the engine is built, matching the precedent set by the
namespace taxonomy ADR landing before pkg-11 implements against it. It is kept
separate from pld-02 deliberately: the decision should be reviewable without
the implementation attached.

## Rejected Alternatives

- **Fold governance rules into `scripts/skills-lint`** — rejected: that script
  has one clear job (validating documented `aet` invocations against real
  parsers); adding unrelated content invariants to a 328-line script conflates
  two concerns.
- **Skip the ADR and encode the grammar only in code** — rejected: the rule
  format is the contract every future invariant is written against; leaving it
  implicit invites drift and re-litigation.
- **Marker-based pytest selection (`@pytest.mark.prose`)** — rejected: still
  requires enumeration plus a guard to catch unmarked tests, so it preserves
  the maintenance surface this workstream exists to delete.

## Files to Modify

- `040-documentation-invariants-as-data.md`, new, in `docs/adr/`
- `docs/adr/README.md`

## Validation Steps

- [ ] Lint passes (`make lint`)
- [ ] Tests pass
- [ ] R-trace coverage: R-1 covered by tasks 1–3
- [ ] No new source files introduced, so no new test coverage is required
- [ ] ADR states the grammar precisely enough that pld-02 can implement it
      without further design decisions
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The ADR is documentation only; nothing depends on it until
pld-02 begins.

## Pipeline

`minimal` — a decision record with no code surface.

---

*Stage: implemented*
*Next step: run `aet-qa`*

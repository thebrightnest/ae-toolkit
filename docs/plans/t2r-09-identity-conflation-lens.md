---
id: t2r-09-identity-conflation-lens
size: M
work_class: normal
blocked_by:
  - t2r-08-boundary-contract-lens
pipeline: standard
security_review: required
security_review_reason: adds a new mechanical check to the gate path every merge depends on
docs_sync: required
docs_sync_reason: adds an optional plan-frontmatter key documented in the plan template
identity: [{entity: project, identifiers: [projectId, projectPath, projectUuid, projectUUID, project_id, project_uuid], persists: projectId}, {entity: session, identifiers: [sessionId, sessionUuid], persists: sessionUuid}]
---

# Plan: Identity-Conflation Lens — Dual Identifiers Must Name Which One Persists

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-7). Evidence:
`content/aet-structural-review/08-consumer-evidence.md` (cause 8) — three
consumer projects independently shipped the same bug: a path or foreign id
passed where a UUID was expected (provider session id vs application UUID,
`projectPath` vs `projectId`, route param vs resolved id); every instance
passed the full gate pipeline. `13-value-snapshot.md` item 4 schedules the
fix as a diff-triggered lens, fired off the changed-file set the way
ADR-049 (`docs/adr/049-validation-scope-from-change-set.md`) already derives
validation scope from `src/aet/change_scope.py`.

**Dependency (blocked_by):** t2r-08-boundary-contract-lens (stem confirmed
against its plan file) builds the first mechanical lens and the carrier
decision (how a lens result enters the gate). t2r-08's actual design: a
single module `src/aet/boundary.py` — no `src/aet/lenses/` package, no
runner registry — with enforcement inside `src/aet/cli/gate.py`: on
`gate submit --stage review` it runs the check over
`change_scope.changed_paths()` and refuses a `pass` verdict in code when
the lens trips. This plan mirrors that design exactly: a single module
`src/aet/identity.py` (same layout), enforced by refusing a `pass` verdict
at submit time inside `src/aet/cli/gate.py`, identically. Shared surfaces:
`src/aet/change_scope.py` (`changed_paths()`, `BASE_REF`, `_git`),
`src/aet/evidence.py` (`SCHEMAS["review"]` with its `findings` list), and
`src/aet/cli/gate.py` (`aet gate submit`, the sole verdict writer post
slc-05).

**Supersession / collision:** PRD Open Question 1 proposes superseding the
parked `docs/plans/cov-02-tdd-coverage-gate.md` and
`docs/plans/cov-04-review-tests-lens.md` with the R-6/R-7 lens plans;
cov-04 is a review-side prose lens (test coverage), adjacent but distinct
from R-7's identifier check. Confirm the supersede disposition at scope
validation; this plan does not modify either cov file.

**Post-slc constraint:** no prose writer around `aet gate submit` or
`aet state set-stage` (ADR-055, slc-05). Enforcement is refuse-pass-in-code:
a fired-but-undeclared lens refuses a `pass` review verdict at
`aet gate submit` (named error, exit 1) — the reviewer does not choose to
submit `fail`; the gate refuses `pass`, same as t2r-08's boundary lens.

**Ledger discipline:** the lens produces no state of its own; its outcome
rides the review verdict, which `aet gate submit` already records as a
`verdict` ledger event (`src/aet/cli/gate.py:311-318`). The taxonomy in
`src/aet/ledger.py` (`ALLOWED_KINDS = cut/stage/verdict/land`) has no
lens-finding kind; extending it is a structural change requiring an ADR and
is explicitly out of scope.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. New module `src/aet/identity.py` implementing the detection half
   of the lens: scan added lines of the diff against `origin/main` (reusing
   `change_scope.BASE_REF` and the `_git` helper pattern) for
   identifier-shaped symbols (`*Id`, `*ID`, `*Uuid`, `*UUID`, `*_id`,
   `*_uuid`, `*Path`, route-param bindings); group matches by entity stem;
   the lens fires when two or more distinct identifiers attach to one
   entity. An undeterminable diff yields an indeterminate finding, never a
   silent pass (ADR-049/ADR-025 fail-safe bias). Unit-tested in
   `tests/test_identity.py` with the four evidenced pairs as
   fixtures — M (traces: R-7)
2. Plan-frontmatter `identity:` declaration block, owned and validated by
   the lens (no `plan_parser` contract change): when the lens fires, the
   plan must carry an `identity:` entry per conflated entity naming both
   identifiers and a `persists:` designation that is one of them; a fired
   lens with a missing or malformed declaration is a gate failure — S
   (traces: R-7)
3. Carrier wiring in `src/aet/cli/gate.py` (mirroring t2r-08's task 3): on
   `gate submit --stage review` (builder and `--evidence` modes alike), run
   the identity check over `change_scope.changed_paths()`; a
   fired-but-undeclared result refuses the verdict with a named error and
   exit 1 even when `--verdict pass` is declared — fail-closed in code, no
   prose writer around the sole writer. On pass, record the lens outcome in
   the review payload's `findings` and in the ledger `verdict` event
   `payload`. Covered by extending `tests/gate/test_gate_submit.py`
   (integration) — S (traces: R-7)
4. Add a `change_scope._PATH_TARGETS` entry mapping `src/aet/identity.py` →
   `tests/test_identity.py` (t2r-08's task-2 pattern) so lens changes run
   targeted tests instead of the full suite; extend
   `tests/test_change_scope.py` for the mapping — S (traces: R-7)
5. Document the optional `identity:` block in
   `.agents/templates/plan-template.md` with one worked example
   (`projectPath` vs `projectId`, persists: `projectId`) — S (traces: R-7)
6. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: R-7 (identity-conflation) is a distinct requirement and
  defect class from t2r-08's R-6 (boundary-contract); each is independently
  reviewable against its own consumer evidence.
- [x] Expected diff (~400 lines across src + tests + template) materially
  exceeds branch/PR/review overhead.
- [x] Cannot share a branch with t2r-08: merging both into t2r-08 would push
  that plan past two size signals (>1 human-day, >600 expected diff lines),
  and the blocker ordering exists precisely to sequence infra before lens.

## Rejected Alternatives

- **Prose lens in `skills/aet-review/SKILL.md`** — rejected: the consumer
  evidence is exactly that declared-prose lenses are not effective
  (`08-consumer-evidence.md:67`; ADR-008 declared the boundary lens as
  prose and it never fired). R-7 requires mechanical firing off the
  changed-file set, not reviewer recall.
- **Declaration-only design (author self-declares `identity:` with no diff
  scan)** — rejected: the trigger then depends on author recall, the same
  failure mode as reviewer recall; the diff scan is what makes the
  requirement fire mechanically.
- **Extend `ledger.ALLOWED_KINDS` with a lens-finding event kind** —
  rejected: a structural taxonomy change requiring its own ADR; the
  `verdict` event already emitted by `aet gate submit` carries the lens
  outcome with the evidence path as `ref`.
- **Fold R-7 into t2r-08 as one plan** — rejected: t2r-08 is already size M
  (the boundary-contract lens plus its gate enforcement); adding R-7 trips
  the >1-day and >600-line split signals.

## Files to Modify

- `src/aet/identity.py` (new)
- `src/aet/change_scope.py` (path-target mapping entry)
- `src/aet/cli/gate.py` (refuse-pass wiring, task 3)
- `.agents/templates/plan-template.md` (document the `identity:` block)
- `tests/test_identity.py` (new)
- `tests/gate/test_gate_submit.py` (extended, task 3)
- `tests/test_change_scope.py` (mapping entry test)

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`make test`)
- [ ] `tests/test_identity.py` (unit, single layer) covers:
  token extraction for each identifier shape; entity-stem grouping; each of
  the four evidenced pairs detected (path vs UUID, provider session id vs
  application UUID, `projectPath` vs `projectId`, route param vs resolved
  id); a single-identifier diff does not fire; a malformed `identity:`
  block (one identifier, or `persists:` not among the named identifiers)
  fails validation
- [ ] Integration (cross-layer, `tests/gate/test_gate_submit.py`): a fixture
  change set with a dual-identifier diff and no `identity:` declaration
  refuses a `pass` review verdict at `aet gate submit` (exit 1, named
  error); adding the declaration lets the submit pass; an undeterminable
  diff yields the indeterminate finding, not a silent pass
- [ ] API boundary tests: not applicable — no frontend ↔ backend surface
  changes
- [ ] `tests/test_change_scope.py` covers the `src/aet/identity.py` →
  `tests/test_identity.py` mapping
- [ ] `grep -rn "identity" skills/*/SKILL.md` shows no prose lens
  instructions — the check exists only in code
- [ ] R-trace coverage: R-7 covered by tasks 1–5
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. The new module and its tests delete cleanly; the
`change_scope` mapping entry and template documentation restore with the
revert. The lens writes no state of its own, so no state cleanup is needed;
verdict events already recorded in the ledger remain valid additive facts.

## Pipeline

`standard` — adds a mechanical check to the gate path; default grouping is
sufficient (no auth, data-model, or dependency surface).

---

*Stage: qa-complete*
*Next step: run `aet-review`*

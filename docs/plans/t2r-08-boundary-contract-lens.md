---
id: t2r-08-boundary-contract-lens
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: extends the review-stage verdict path with a fail-closed override every review gate depends on
docs_sync: required
docs_sync_reason: changes documented aet-review lens behavior and supersedes a parked plan
---

# Plan: Boundary-Contract Lens — Mechanical Gate off the Changed-File Set

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-6). ADR-008 declared the
API boundary contract a hard gate in prose (`aet-tdd`); the consumer data
proves declared-and-not-effective — 25 of 111 consumer defects are this class
(API wrapper objects leaking into component state, snake_case reaching
camelCase, frontend calling nonexistent endpoints). This plan moves the check
into code: when the changed-file set touches both a response shape
(serializer/controller/schema) and a client consumer
(component/repository/api-client), a mechanical check requires a test that
asserts they agree. The trigger reuses the ADR-049 changed-file-set mechanism
(`src/aet/change_scope.py:122` `changed_paths()`).

**Carrier decision (evaluated against `src/aet/evidence.py` SCHEMAS and
`src/aet/workflows/software.json`):** the lens rides the existing **review**
verdict via `aet gate submit` (the slc-05 sole-writer path), enforced in code
inside `src/aet/cli/gate.py` — not a new gate kind. A new kind would require a
SCHEMAS entry, a new `software.json` stage (stage ordering, session_groups),
`KIND_TO_STAGE`/`KIND_TO_SKILL` mappings, an owning skill, and a frontmatter
gate key; the check is review-shaped (the `review` schema already carries
`findings: list`), and review is an ungated always-run stage
(`src/aet/gate.py:22`). The `review` SCHEMAS entry is deliberately **not**
extended — adding a required key would invalidate every existing review
payload; the lens outcome rides in `findings` and in the ledger verdict-event
`payload` (the taxonomy in `src/aet/ledger.py` supports structured payloads on
`verdict` events; no new event kind needed).

**Supersession:** parked `docs/plans/cov-04-review-tests-lens.md` (footer
`*Stage: plan-approved*`, unimplemented as a plan) is SUPERSEDED by this plan.
Its part (a) — new-file coverage completeness — already landed as prose in
`skills/aet-review/SKILL.md` (Tests lens) and
`skills/aet-review/references/test-coverage-check.md` §1–2; its part (b) — the
API boundary check — is subsumed by this plan's code gate. Reusable intent
carried over: the shape/consumer path heuristics and the boundary-test marker
vocabulary (`msw`, `nock`, `Http::fake`, `mirage`) from
`test-coverage-check.md` §3 seed the classifier defaults. Formal closure of
cov-04 (superseded → abandoned) is queue/state bookkeeping at scope
validation, not a diff task here.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. New module `src/aet/boundary.py`: path classifier (default pattern tables
   for response-shape files — serializers/controllers/schemas/resources/DTOs —
   and client-consumer files — components/repositories/api-clients/hooks/stores;
   overridable via a `boundary_contract` key in `.agents/aet-config.json`,
   the established per-project config surface), and
   `check(paths) -> result` that pairs changed shape files with changed
   consumer files and searches test files for an agreement test (a test
   referencing both sides, or using the boundary-mock marker vocabulary).
   Covered by new `tests/test_boundary.py` (unit). — M (traces: R-6)
2. Register the new module in the `src/aet/change_scope.py` `_PATH_TARGETS`
   table (`src/aet/boundary.py` → `tests/test_boundary.py`) so ADR-049 scoping
   stays complete. — S (traces: R-6)
3. `src/aet/cli/gate.py`: on `gate submit --stage review` (builder and
   `--evidence` modes alike), run `boundary.check()` over
   `change_scope.changed_paths()`; when the lens trips (both sides touched, no
   agreement test), refuse the verdict with a named error and exit 1 even when
   `--verdict pass` is declared — fail-closed in code, no prose writer around
   the sole writer. On pass/n-a, record the lens outcome in the review
   payload's `findings` and in the ledger `verdict` event `payload`.
   Covered by extending `tests/gate/test_gate_submit.py` (integration). — M
   (traces: R-6)
4. Update `skills/aet-review/SKILL.md` Tests lens to state the
   boundary-contract half is enforced mechanically at `aet gate submit`
   (reviewer judgment no longer carries it); update
   `skills/aet-review/references/test-coverage-check.md` §3 to point at the
   code gate, retiring its shell heuristic. — S (traces: R-6)
5. Add ADR-057 (new file `057-boundary-contract-lens-in-code.md` under
   `docs/adr/`) recording the carrier
   decision and the supersession of cov-04's part (b); register it in the
   `docs/adr/README.md` index (056 is allocated to t2r-06's
   `056-adr-relations-as-frontmatter.md`). — S (traces: R-6)
6. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: the boundary-contract defect class is independently
  shippable; sibling R-7 (identity-conflation lens) shares the trigger
  mechanism but analyzes plans/diffs for duplicate identifiers — a different
  input surface and a different failure class, planned separately (t2r-09).
- [x] Expected diff (~550 lines across src + tests + skills + ADR) materially
  exceeds branch/PR/review overhead.
- [x] Cannot share a branch with t2r-09 without coupling two independent gate
  behaviors into one review.

## Rejected Alternatives

- **A new gate kind (`boundary`) in `evidence.SCHEMAS` + a new
  `software.json` stage** — rejected: schema + workflow + session-group +
  owning-skill surface for a check that is review-shaped; the review stage
  already always runs and already carries `findings`. Cost high, no added
  signal.
- **Enforce at the qa stage** — rejected: the qa schema is test-count-shaped
  (`tests_total/passed/failed`); producer↔consumer agreement is a diff-pairing
  question, and the changed-file set is final by review.
- **Prose-only lens strengthening (the cov-04 approach)** — rejected: ADR-008
  already declared this in prose and the consumer log proves
  declared-and-not-effective (25/111 defects passed the full pipeline green).
- **A standalone `aet check boundary` command without gate enforcement** —
  rejected: whether it runs becomes reviewer recall again; the check must fire
  structurally on the verdict path.
- **Extend the `review` SCHEMAS entry with a `lenses` key** — rejected:
  schema keys are required keys; adding one invalidates every existing review
  verdict payload. The outcome rides in `findings` and the ledger payload.

## Files to Modify

- `src/aet/boundary.py` (new)
- `src/aet/change_scope.py`
- `src/aet/cli/gate.py`
- `tests/test_boundary.py` (new)
- `tests/gate/test_gate_submit.py` (extended)
- `skills/aet-review/SKILL.md`
- `skills/aet-review/references/test-coverage-check.md`
- `docs/adr/` — new file `057-boundary-contract-lens-in-code.md`
- `docs/adr/README.md` (index registration)

## Validation Steps

- [ ] Lint passes (`make lint-py`); `make validate` green
- [ ] `tests/test_boundary.py` covers `src/aet/boundary.py` (unit):
  classification of shape vs consumer paths, config-table override, pairing
  fires only when both sides are in the changed set, agreement-test detection
  by module reference and by marker vocabulary, no-fire on one-sided diffs
- [ ] `tests/gate/test_gate_submit.py` (integration): a review `pass` submit
  is refused (exit 1, named error) when a fixture diff touches a shape and a
  consumer with no agreement test; accepted when an agreement test exists;
  unchanged when the diff touches only one side; identical behavior in builder
  and `--evidence` modes
- [ ] Ledger `verdict` event payload records the lens outcome for a review
  submit (integration, alongside the existing ledger assertion in
  `tests/gate/test_gate_submit.py`)
- [ ] Structural: `evidence.SCHEMAS["review"]` unchanged — a pre-existing
  review payload still validates (no new required key)
- [ ] Reading the updated Tests lens in `skills/aet-review/SKILL.md`: the
  boundary-contract check is attributed to the mechanical gate, not reviewer
  recall
- [ ] R-trace coverage: R-6 covered by tasks 1–5; no task cites another R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. `aet gate submit` returns to prior behavior; the skill and
reference edits restore with the revert; ledger events already written remain
valid additive facts.

## Pipeline

`standard` — extends the verdict-ingestion path the review gate depends on
(risk override per ADR-047, same as slc-05).

---

*Stage: qa-complete*
*Next step: run `aet-review`*

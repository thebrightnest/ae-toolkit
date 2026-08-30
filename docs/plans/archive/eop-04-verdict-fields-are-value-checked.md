---
id: eop-04-verdict-fields-are-value-checked
size: S
work_class: critical
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: Tightens the fail-closed gate ADR-019 makes the sole arbiter of stage completion.
docs_sync: required
docs_sync_reason: Changes what a verdict payload must contain, which the gate-submitting skills describe.
---

# Plan: A Verdict Field That Gates a Stage Is Value-Checked

## Context

PRD: docs/prds/evidence-over-proxy-prd.md
Decision: ADR-072 (A Proxy Is Not Evidence), decision 4 — well-formed is not
attested. Relates to ADR-019 (structured gate evidence) and ADR-025.

`evidence.SCHEMAS` (`src/aet/evidence.py`) is a map of field name to Python
**type** — `dict[str, dict[str, type]]`. Validation therefore confirms that
`summary` is a `str`, not that it says anything. A payload carrying
`summary: "pending"` validates and is written as a passing verdict.

ADR-019 makes the structured verdict the fail-closed arbiter of whether a stage
completed. The gate cannot distinguish a real attestation from a well-typed
placeholder, so the strongest guarantee in the pipeline rests on a type check.
The fields that decide gating — `verdict`, and `tree_hash` since ADR-025 — are
checked; the field carrying the substance is not.

The check belongs in `validate_verdict`, where the `verdict` enum is already
enforced, not in `SCHEMAS`: the schema map is a type map by construction and
expressing a value constraint would change its type.

## Intake Triage

- [x] Demonstrable defect, recorded in
      `content/backlog/debt-evidence-fields-are-not-value-checked.md`
- [x] Routed here because it changes the verdict contract every gate consumer
      reads, and the PRD's ADR states the rule it conforms to

## Task List

1. Add a substance constraint for gating text fields in `validate_verdict`,
   beside the existing `verdict` enum check: empty, whitespace-only, and a
   closed deny-list of placeholders are refused — S (traces: R-5)
2. Return the same shape of refusal the enum check returns, so every existing
   caller reports it without change — S (traces: R-5)
3. Unit tests: a placeholder is refused, a real summary passes, a payload with
   only `verdict` and `tree_hash` behaves as before, and the refusal reaches
   `aet gate submit` as a non-zero exit — S (traces: R-5)
4. State the constraint in the skills that submit verdicts, so an agent writes a
   real summary rather than discovering the refusal — S (traces: R-5)
5. Merge branch to main and verify integration — S

### Floor Check

- [x] The change is limited to one subsystem and maintains no architectural invariant
- [ ] Expected diff is below the calibrated floor threshold
- [ ] `Files to Modify` substantially overlaps a sibling it is ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

One box checked: the fail-closed contract is ADR-019's and unchanged; this
tightens one field's validation inside it.

## Rejected Alternatives

- **A minimum-length rule instead of a deny-list** — rejected per the PRD's open
  question: a length floor invites a longer placeholder and reads as a substance
  guarantee it cannot give. A deny-list is honest about being a heuristic.
- **Change `SCHEMAS` to hold validators instead of types** — rejected: it changes
  a published type for one field's benefit and pushes value policy into a
  structural map.
- **Stamp `summary` unconditionally from the stage record** — rejected: the
  source proposes it as an alternative, but a generated summary attests nothing
  and would make the placeholder problem invisible rather than absent.

## Files to Modify

- `src/aet/evidence.py`
- `skills/aet-qa/SKILL.md`
- `skills/aet-verify/SKILL.md`
- `tests/evidence/test_validate_verdict.py`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] Every field named in the deny-list check is one an existing gate reads
- [ ] No previously valid verdict in the repo's fixtures becomes invalid except
      those deliberately carrying placeholders
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Verdict validation returns to type-only, which is the state
every existing record was written under, so no stored verdict becomes unreadable.

## Pipeline

`standard` — this tightens the gate that decides stage completion.

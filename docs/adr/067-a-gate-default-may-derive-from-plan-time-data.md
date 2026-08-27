---
subject: gate-default-derivation
relates: [20, 61]
---

# A Gate Default May Derive from Plan-Time Data

## Status

Accepted (2026-08-27). Relates to ADR-020 (Routing Decided at Plan Time and
Enforced as Data) and ADR-061 (The Record Is the Plan After Intake). Implements
R-6 and R-7 of the Plan Obligations Hardening PRD
(`docs/prds/plan-obligations-hardening-prd.md`).

## Context

`src/aet/workflows/software.json` defines the pipeline stages. `aet ship merge`
refuses a `work_class: critical` task if verification evidence
(`.agents/verify/<task>-evidence.md`) is missing. Previously, no stage in the
software workflow produced verification evidence, meaning critical tasks had to
produce evidence out of band, and ship-time refusal arrived only after every
expensive stage had completed.

The conditional live verification PRD (`docs/prds/conditional-live-verification-prd.md`)
established that live verification is intended for critical tasks only and
explicitly rejected running it universally on normal and trivial tasks.

Existing gated stages (`security_review`, `docs_sync`) resolve with a fail-safe
rule: an omitted frontmatter key defaults to `required` (the stage runs), and
skipping requires an explicit `skipped` value paired with a recorded reason
(`security_review_reason` / `docs_sync_reason`). If a `verify` stage used that
same absent-key-means-run default, it would run on every plan where the key was
omitted—producing the very universality the verification PRD rejected.

The pipeline needed a mechanism where a stage's default can be chosen by the
workflow definition and derived from the plan's `work_class`—plan-time data,
ensuring ADR-020's rule that routing is decided at plan time and enforced as
data continues to hold.

## Decision

**A gated stage's default behavior may derive from another plan-time frontmatter
key (`work_class`). The `work_class` declaration is itself the recorded
plan-time judgment.**

1. **Workflow stage schema includes `gate_default`.** The workflow stage schema
   supports an optional `gate_default` field with a closed two-value vocabulary:
   `required` (the default when omitted) and `critical-only`.
2. **`stage_enabled` resolves `critical-only` defaults.** When a gate key is
   absent from the plan frontmatter:
   - A stage with `gate_default: required` runs (fail-safe).
   - A stage with `gate_default: critical-only` runs if `work_class: critical`
     and skips for `normal`, `trivial`, or `unclassified`.
3. **Explicit frontmatter keys are authoritative.** An explicit
   `verify: required` runs regardless of `work_class`. An explicit
   `verify: skipped` skips and requires a `verify_reason`, preserving the
   intake validation rule that explicit overrides carry a recorded justification.
4. **Default-derived skips carry no separate reason.** The `work_class`
   declaration is the recorded judgment at plan time. A normal or trivial plan
   skips verification by virtue of its classification without requiring a
   redundant `verify_reason`.

## Consequences

- **Easier:** Critical plans automatically route through the `aet-verify` stage
  and produce the evidence required by `aet ship merge`.
- **Easier:** Normal and trivial plans do not run verification by default and do
  not require boilerplate `verify: skipped` + `verify_reason` declarations.
- **Easier:** The engine remains free of runtime heuristic judgments; all
  decisions evaluate deterministic plan-time frontmatter data against declared
  workflow schema.
- **Neutral:** Explicit overrides remain available and fully validated: setting
  `verify: skipped` on a critical plan requires a written reason, and setting
  `verify: required` on a normal plan runs verification.

## Alternatives Considered

1. **Require `verify: skipped` on every normal plan** — Rejected: would require
   authoring overhead on every standard plan, and legacy plans without the key
   would run verification under the old absent-key-means-run rule.
2. **Warn at run start without adding a workflow stage** — Rejected: moves the
   surprise earlier without giving the obligation a producer, leaving evidence
   to be written out of band.
3. **Create a separate `software-critical.json` workflow file** — Rejected:
   multiplies workflow definitions across orthogonal dimensions (workflow type vs
   risk classification).
4. **General frontmatter expression DSL in workflow schemas** — Rejected: a
   closed two-value vocabulary covers the requirements, and general expression
   evaluation reintroduces complexity and runtime variability that ADR-020
   specifically avoids.

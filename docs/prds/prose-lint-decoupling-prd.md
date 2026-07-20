# PRD: Decouple pytest from Repo Prose

## Overview

`make validate` is this repo's only safety net — CI is ruled out on cost
(GitHub charges for Actions) — so the gate has to be complete and fast at the
same time. The prose-only fast path shipped on 2026-07-20 (`src/aet/change_scope.py`,
merged to main 2026-07-21) delivers the speed, but only by enumerating five
test modules that assert
against the repo's own Markdown, policed by an AST-based guard test that
re-derives the list from the test tree. That enumeration exists for one reason:
documentation invariants are currently expressed as pytest assertions. Every
prose assertion in the suite reduces to one of four patterns — substring
present, substring present within a named section, substring absent, or a set
of substrings present — which is a declarative grammar wearing test-code
clothing. Moving those invariants into a rules file evaluated by a new
`aet docs lint` stage, and moving the one genuine repo-health check (the plan
corpus classifier) into an `aet plans lint` stage, removes pytest's dependency
on Markdown entirely. The fast path then becomes safe *by construction* —
prose-only changes run no pytest at all — instead of safe *by enumeration*, and
the allowlist plus its guard get deleted rather than maintained.

## Goals

- pytest has zero dependencies on repo Markdown: no test reads `docs/`,
  `*/SKILL.md`, or any other prose file from the checkout.
- A prose-only change runs no pytest at all, and `change_scope.py` reduces to
  that single rule — `DOC_COUPLED_TESTS` and the AST guard are deleted, not
  maintained.
- Governance invariants become data: a new must-contain rule is a line in a
  rules file, not a new Python test.
- Failure messages stay at least as diagnostic as today's assertions, which
  name the file, the expectation, and why it matters.

## Non-Goals

- **CI.** Ruled out on cost; this PRD assumes local validate remains the only
  gate and is designed around that constraint rather than deferring to it.
- **The `--dist=loadgroup` serialization.** Nine files share one xdist group,
  costing ~60s on every code-touching validate (100s vs 40s measured
  2026-07-20). That is a larger speed lever than this workstream and is tracked
  separately — this PRD does not touch xdist configuration.
- **Clock injection into orchestrator timeouts.** The base cost of the slowest
  tests is real wall-clock sleeping; worth fixing, unrelated to prose coupling.
- **Re-litigating what the invariants assert.** This is a relocation. Every
  rule ports 1:1; changing or dropping an invariant is out of scope and must be
  raised separately.
- **Markdown style linting.** `markdownlint` and `prettier` already own format;
  this covers content invariants only.

## Requirements

- **R-1**: An ADR records the principle — documentation invariants are declared
  as data and enforced by a lint stage, not asserted in the unit-test suite —
  along with the rule grammar and the boundary against `skills-lint` (which
  validates documented `aet` invocations against real parsers and keeps that
  single job).
- **R-2**: A declarative rule format covers every pattern present in the
  current assertions: `must_contain`, `must_not_contain`, section-scoped
  variants of both (`section:` narrows matching to the content under a named
  heading), and path assertions (`path_exists`, `path_absent`) for the layout
  checks in `tests/test_scripts_layout.py`. Rules are data, parsed with PyYAML
  (already a dependency).
- **R-3**: `aet docs lint` evaluates the rule file and joins `make validate`
  before pytest, so the cheap check fails first. Naming follows the
  noun-scoped, nested-verb convention established by gib-06 and carried by
  `docs/prds/namespace-consolidation-prd.md`, not a hyphenated `aet docs-lint`.
- **R-4**: The prose assertions in `tests/skills/test_aet_qa.py`,
  `tests/skills/test_aet_review.py`, `tests/ship/test_merge_governance.py`, and
  `tests/test_scripts_layout.py` are ported to rules 1:1 and removed from
  pytest. A port is complete only when breaking the underlying prose is shown
  to fail `aet docs lint` for each ported invariant.
- **R-5**: `aet plans lint` runs the corpus classifier currently in
  `tests/orchestrator/test_status_liveness_contract.py::test_corpus_classifier_matches_known_live_set`
  — the one doc-coupled check that executes real `plan_parser`/`plan_validate`
  logic and therefore cannot become a string rule — over the live `docs/plans/`
  corpus, and joins `make validate`. That single test is removed from pytest;
  the module's other ~200 lines of temp-dir unit tests stay.
- **R-6**: `change_scope.py` is reduced to "prose-only change → run no pytest".
  `DOC_COUPLED_TESTS`, `pytest_targets`, and the AST guard in
  `tests/test_change_scope.py` are deleted; the classifier, its fail-safe
  behavior, and their tests remain.
- **R-7**: A guard prevents regression: pytest must not regain a dependency on
  repo prose. The check fails when any module under `tests/` reads Markdown
  from the checkout outside `tests/`.

## User Stories

- As a maintainer editing a plan's frontmatter, I want validate to finish in a
  few seconds so that marking a plan merged is not gated on a 40-second suite
  (satisfies: R-6)
- As a maintainer adding a governance invariant, I want to add a line to a
  rules file rather than write a test module so that the invariant is cheap to
  state (satisfies: R-2, R-3)
- As a maintainer, I want a prose regression to fail validate with a message
  naming the file and the missing expectation so that the fix is obvious
  without reading the linter (satisfies: R-2)
- As a future contributor, I want the fast path to stay safe without my
  remembering an allowlist so that correctness does not depend on discipline
  (satisfies: R-6, R-7)

## Acceptance Criteria

- [ ] An ADR states the governance-as-data principle and the `skills-lint`
      boundary (satisfies: R-1)
- [ ] The rule format expresses every currently-asserted invariant, including
      section-scoped and negative rules (satisfies: R-2)
- [ ] `aet docs lint` runs in `make validate` ahead of pytest (satisfies: R-3)
- [ ] Every ported invariant is demonstrated to fail `aet docs lint` when the
      underlying prose is broken (satisfies: R-4)
- [ ] `aet plans lint` runs the corpus classifier in `make validate`; the
      corresponding pytest case is gone and the module's unit tests remain
      (satisfies: R-5)
- [ ] No module under `tests/` reads Markdown from the checkout outside
      `tests/` (satisfies: R-4, R-5, R-7)
- [ ] A prose-only change runs zero pytest tests and completes validate in
      under 10 seconds (satisfies: R-6)
- [ ] `DOC_COUPLED_TESTS` and the AST guard no longer exist (satisfies: R-6)

## Technical Notes

- **Precedent to follow, not extend.** `scripts/skills-lint` (328 lines)
  already lints Markdown against code reality and has a severity model
  (`--legacy=warn|error`) and an escape hatch (`<!-- aet-lint: off -->`). Reuse
  those conventions in the new stage; do not fold governance rules into
  skills-lint, whose job is validating documented `aet` invocations against
  `SUBCOMMANDS` and each target's `build_parser()`.
- **Ordering.** Both new stages are cheap and must run before pytest in
  `validate`, preserving the existing fail-fast structure.
- **Sequencing.** R-4 and R-5 must both land before R-6: `change_scope` can
  only drop the allowlist once nothing in pytest reads prose. R-6 landing early
  would silently skip live doc-coupled tests.
- **Rule file location.** Alongside the other agent-facing config in
  `.agents/`; the exact filename is a plan-level detail.
- **Message quality is a requirement, not a nicety.** Today's assertions carry
  messages like "SKILL.md should default to impact-scoped tests". The rule
  format needs a per-rule `reason` (or equivalent) so failures stay that
  legible — a bare "substring not found" is a regression.
- **Expected shape.** Roughly three plans: the rule engine and ADR; the port
  plus corpus-check move; the `change_scope` simplification and regression
  guard. Final split is `aet-plan`'s call.
- **Measured baseline (2026-07-20).** Full suite ~40s at `--dist=load`, ~100s
  at `--dist=loadgroup`; non-pytest validate stages ~2.7s; the five doc-coupled
  modules ~1.5s. A prose-only validate today is ~5s and should land near ~3s.

## Open Questions

- Should `aet docs lint` treat unknown or unmatched rules as errors or
  warnings? Fail-closed matches the gate's posture, but a stale rule pointing at
  a renamed file would then block unrelated work. A `path_absent`-style rule
  for retired files may cover it.
- Do the layout checks (R-2 path assertions) belong in `aet docs lint` at all,
  or in a repo-hygiene stage alongside `aet plans lint`? They are not prose;
  they ride here only because `test_scripts_layout.py` also asserts README
  content.
- Is there a case for the rules file being per-skill (colocated with each
  `SKILL.md`) rather than central? Central is simpler to audit; colocated
  survives skill extraction better, which matters given the pkg-* packaging
  direction.

---

*Stage: prd-draft*
*Next step: review and approve, then run `aet-validate-scope`*

---
id: cdc-03-cli-syntax-lint
size: S
work_class: normal
blocked_by: []
pipeline: minimal
security_review: skipped
security_review_reason: Removes a prose section and adds declarative documentation lint rules; no executable surface.
docs_sync: required
docs_sync_reason: Edits skill prose and adds governance rules to `.agents/doc-rules.yaml`; both the removal and the rule rationale must be documented.
---

# Plan: CLI-Syntax Lint and the Last Hand-Copied Option Table

## Context

- PRD: `docs/prds/cli-discovery-cost-prd.md` (R-4)
- Principle: R-10 of `docs/prds/structural-review-tier-2-prd.md` —
  CLI references are generated from the command tree or absent, never hand-copied.
- Grammar and lint boundary: ADR-040 (documentation invariants are data).
- Precedent: archived plan `t2r-11-generated-cli-reference` performed the bulk cleanup.

`t2r-11` removed the Typer-format mirrors, and a scan for those markers
(`[default:`, `*str*`, `--flag <str>`) returns 0. A second scan for *hand-written*
option tables found the one it missed: `skills/aet-evolve/references/aet-retro.md:30`
carries a `## Options` section hand-copying six `aet retro` and `aet metrics` flags
with their defaults. It is currently accurate — which is precisely the danger, since
nothing keeps it that way. A stale flag in prose is worse than an absent one: the
agent trusts it and fails on it.

This plan removes that section and adds the guard that keeps it removed, in one
commit, so the rule is never added to a tree that violates it.

**Scope boundary.** Only mechanically-derivable syntax goes. Skill prose correctly
keeps third-party flags (`git rev-list --count`, `pytest --dist`) outside the `aet`
tree, and correctly keeps `aet` flag *semantics* that `--help` lacks — for example
`skills/aet-work/references/queue-commands.md:70`, "`--follow` does **not** tail or
stream the run log". Both stay.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The existing `## Options` section is accurate today; this is drift prevention, not a bug fix

## Task List

1. Remove the two `## Options` blocks from `skills/aet-evolve/references/aet-retro.md`
   and repoint the file at `aet retro --help` / `aet metrics --help`, preserving the
   surrounding workflow guidance — S (traces: R-4)
2. Add `must_not_contain` rules to `.agents/doc-rules.yaml` for the heading
   `## Options` and the verbatim-paste markers `*str*`, `*boolean*`, `*int*`,
   `*path*`, `<str>`, `<int>`, `[default:`, each with a reason citing the
   generated-or-absent principle — S (traces: R-4)
3. Add tests: lint fails on a fixture containing a hand-copied option table; lint
   passes on the post-removal `skills/` tree; lint does not fire on fixtures
   containing third-party flags or `aet` flag semantics — S (traces: R-4)
4. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines

### Floor Check

- [x] Expected diff is below the calibrated floor threshold (≤ 50 headline lines)
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

One signal checked. Justification for standing alone: it shares no files with
`cdc-01`/`cdc-02` (`skills/` and `.agents/`, not `src/aet/cli/`) and has no
dependency on either, so folding it in would couple an independent governance rule
to a CLI rendering change and delay it behind `cdc-01` for no benefit.

## Rejected Alternatives

- **Put the rule in `scripts/skills-lint` instead of `aet docs lint`** — rejected:
  ADR-040 draws the boundary as "skills-lint checks that documentation matches the
  CLI surface; docs lint checks governance invariants." R-4 never consults the
  command tree — it is a pure content policy — so it is a governance invariant.
- **Express the rule as a regex over option signatures** — rejected: ADR-040 fixes
  the grammar at exactly four substring-based types. Literal markers stay inside the
  grammar and need no ADR amendment.
- **Use `(default: ` as a blocked literal** — rejected: 7 occurrences in `skills/`,
  4 of them legitimate prose about environment variables and tier defaults. It would
  fire on correct content.
- **Ship the lint with an `<!-- aet-lint: off -->` escape hatch around the existing
  section** — rejected: it institutionalizes the exact thing the rule exists to
  prevent.
- **Strip all command references from skill prose** — rejected: the audit found the
  remaining content is fail semantics and when-to-use guidance, not duplicated
  syntax. Removing it would delete the judgment layer skills exist to carry. Moving
  that content into help text is parked as
  `docs/ideas/enrich-cli-help-at-the-source.md`.

## Files to Modify

- `skills/aet-evolve/references/aet-retro.md`
- `.agents/doc-rules.yaml`
- `tests/` (doc-lint fixtures and tests)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-4 covered by ≥ 1 task
- [ ] `aet docs lint` verified green against the post-removal `skills/` tree
- [ ] False-positive fixtures (third-party flags, flag semantics) asserted as passing
- [ ] `aet-retro.md` still documents when and why to run the command after the removal
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The rules are declarative and additive and the prose removal is a
content edit; reverting restores both prior lint behavior and the removed section with
no state or data implications.

## Pipeline

`minimal` — S-sized prose edit plus declarative rules and tests.

---

_Stage: plan-approved_

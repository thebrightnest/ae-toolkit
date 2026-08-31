---
subject: documentation-invariants
supersedes: [56]
---

# A Fact a Document Copies From Code Is Checked Against That Code

## Status

Accepted (2026-08-31). Extends ADR-040 (Documentation Invariants Are Data) and
supersedes ADR-056 (ADR Relations Are Declared in ADR Frontmatter), carrying its
decisions forward with one changed: frontmatter becomes required, not optional.

Implements the decision record of
[docs/prds/document-conformance-lint-prd.md](../prds/document-conformance-lint-prd.md).

## Context

ADR-040 made documentation invariants data and built `aet docs lint` to evaluate
them. ADR-056 extended the grammar with `unique_live_subject` so the ADR corpus
would check itself. Both were the right shape. Neither is reading most of what it
was built to read.

`unique_live_subject` skips any ADR with no frontmatter — by explicit instruction
in the evaluator — and **39 of 72 records carry none**. Because the rule is keyed
on `subject`, two records numbered 072 declared different subjects and passed it:
nothing in the corpus keys on the ADR *number*, so for a period "ADR-072" did not
identify a record, and an incident report cited the wrong one. Separately,
`aet context`'s digest resolver detects a dangling `supersedes:` and had been
printing `CONFLICT supervision-uniformity: dangling supersedes: 53` on every
session start; it prints, it does not gate.

The corpus therefore had two readers of different strictness, where the strict one
only warned and the gating one was blind to more than half its input.

The same shape holds outside the ADR corpus. Skill prose names
`.agents/work-queue.json`, a path the `git-refs` backend stopped writing, in ~50
places. PRDs carry 132 `path.py:NN` anchors that `aet-sync-docs` consumes, four of
five of which resolved to unrelated code by the time one initiative closed — and
three of the *symbols* those anchors named no longer existed at all.

On 2026-08-30 two of these were repaired by hand. The same afternoon, in the same
files, the class produced two fresh instances. Repair does not close it.

## Decision

1. **A fact a document copies from code is checked against that code.** Where a
   document asserts something the tree owns — a path, a relation, a symbol — a
   rule reads the tree, never a copy maintained beside it. This is the general
   form of the principle `scripts/skills-lint` already applies to the CLI surface
   by importing the command tree instead of listing it.

2. **The rule grammar gains three types**, per ADR-040's requirement that a new
   rule type be recorded in an ADR:
   - `adr_corpus_integrity` — duplicate numbers, dangling `supersedes:`/`relates:`,
     relations naming a superseded record, and missing `subject:`.
   - `retired_path_absent` — references to paths the toolkit has retired, read from
     `AET_RETIRED_IGNORED_PATHS`.
   - `code_anchor_resolves` — refuses `path:NN` line anchors; requires a symbol
     that resolves to a definition in the named file.

3. **ADR frontmatter is required, not optional.** This changes ADR-056 decision 1,
   which said every ADR *may* declare `subject:`. A record with no `subject:` is
   invisible to the digest and cannot be the target of any relation without
   dangling, so optionality is what made the corpus half-checked. `supersedes:` and
   `relates:` remain optional — absence of a relation is a fact, not a gap.

4. **ADR-056's decisions 2, 4 and 5 are carried forward unchanged:** supersession
   is global; `000-template.md` and `README.md` are never evaluated; malformed
   frontmatter fails closed.

5. **Supersession logic has one implementation.** `adr_corpus_integrity` consumes
   `context_digest`'s existing resolver rather than reimplementing it. A second
   implementation of the same rule beside the first is the defect class this record
   exists to close.

6. **A new rule lands at warning severity and ratchets to error once its sweep has
   landed.** `skills-lint`'s `--legacy=warn|error` switch is the precedent. A rule
   that fails the build on the day it lands is switched off rather than obeyed, and
   a switched-off rule is worse than none because it reads as coverage.

7. **A deliberate divergence is declared, not tolerated.** `aet docs lint` gains
   the escape marker `skills-lint` already spells, `<!-- aet-lint: off -->` …
   `<!-- aet-lint: on -->`. Prose that names a retired path on purpose — migration
   guides — or cites code as it stood at a decision says so explicitly and
   greppably. This mirrors ADR-072: where a check must be relaxed, the call site
   names the divergence it accepts.

## Consequences

- 39 ADRs need `subject:` frontmatter before rule 3 can move to error severity.
  Backfilling is not mechanical: ADR-053's supersession of ADR-031 is partial and
  stated in prose, and declaring it as data would create a new dangling edge, since
  ADR-031 carries no frontmatter either.
- ~50 retired-path references and 132 code anchors must be swept, each behind its
  own rule, each needing per-file judgment.
- `aet docs lint` becomes the single engine for document governance. ADR-040's
  boundary against `scripts/skills-lint` is applied rather than amended: the CLI
  surface stays with `skills-lint`; content governance is here.
- The ADR corpus stops being self-describing only by convention. An author who
  omits frontmatter is refused at `make validate` instead of silently leaving the
  digest.

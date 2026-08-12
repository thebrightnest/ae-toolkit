---
id: t2r-07-context-digest-injection
size: M
work_class: normal
blocked_by:
  - t2r-04-aet-context-command
  - t2r-06-adr-frontmatter-docs-lint
pipeline: standard
security_review: skipped
security_review_reason: read-only digest over repo docs; no auth, data-model, API, or dependency surface
docs_sync: required
docs_sync_reason: implementation may diverge from plan; the R-5 divergence summary must be captured in the PRD
---

# Plan: Current-Rules Digest and Durable-Insight Injection at Prime Time

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-5). Today the rules an
agent should follow are filed, not injected: ADRs record decisions as prose
(`## Status` headings), and `.agents/learnings.jsonl` accumulates entries
that no code reads. R-5 makes both generated and injected: a current-rules
digest built from ADR frontmatter (`subject:`/`supersedes:`), and durable
insights (mined learnings) injected into `aet context` output at prime time.

Verified repo state (2026-08-10):

- `aet context` does not exist yet — `src/aet/cli/main.py` registers no
  context typer. It is delivered by blocker **t2r-04-aet-context-command**; this plan extends its
  output shape with two fields (`rules_digest`, `durable_insights`). If
  t2r-04-aet-context-command's shipped shape differs, reconcile at scope validation.
- No ADR carries `subject:`/`supersedes:` frontmatter yet (grep over
  `docs/adr/` — 57 files, `## Status` prose only). Blocker **t2r-06-adr-frontmatter-docs-lint** adds
  the frontmatter, extending ADR-040's invariants-as-data grammar. The digest
  parser must tolerate ADRs without `subject:` (excluded) so the feature
  degrades gracefully during t2r-06-adr-frontmatter-docs-lint's migration.
- `aet mine-learnings` (`src/aet/cli/mine_learnings.py`) reads the telemetry
  archive only; it has **not** gained a learnings reader. Per PRD Open
  Question 5 (default proposal), this plan ships the degrade path: a top-N
  most-recent reader over `.agents/learnings.jsonl` directly, behind a
  selector interface the recurrence-threshold promotion mechanism plugs into
  when item 3 lands.
- Zero code reads `.agents/learnings.jsonl` today (`evidence.py:237` lists
  it only as a docs-exact freshness path; `retro.py:311` mentions it in
  prose). The repo copy holds 54 JSON lines plus 4 non-JSON lines (figures
  verified by the t2r-01 author, 2026-08-10): the dominant/current schema
  is `timestamp` (44 entries), 10 legacy entries use `date`, 5 carry
  `recurrence`, and one `context`/`lesson`/`source` outlier exists.
  t2r-01's writer canonicalizes the `timestamp` shape, so readers tolerate
  legacy `date`; the PRD's "169" counts the wider corpus.
- `plan_parser.parse_frontmatter()` (`src/aet/plan_parser.py:102`) is the
  existing frontmatter parser; the digest reuses it rather than adding a
  second parser.

Post-slc boundary (ADR-055): this plan adds no verdict, stage, or footer
writer — it extends a read-only context command. Ledger emission was
considered and rejected (see Rejected Alternatives); the taxonomy
(`src/aet/ledger.py:28`: `cut`/`stage`/`verdict`/`land`) covers state
transitions, and a read-only generation produces no state.

Collision boundary: replacing aet-prime's `LEARNINGS` preamble line and the
other Shared Preamble blocks with `aet context` consumption is **t2r-05**
(R-4), not this plan. This plan only places the digest and insights into the
`aet context` output.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. [x] New module `src/aet/context_digest.py`: ADR reader — walk `docs/adr/*.md`,
   parse frontmatter via `plan_parser.parse_frontmatter`, collect `subject:`
   and `supersedes:`; ADRs without `subject:` are excluded, never errors —
   S (traces: R-5)
2. [x] Chain resolution in `src/aet/context_digest.py`: group by subject,
   resolve the `supersedes:` chain to the single live ADR (the
   rule-as-it-stands). Cycles, dangling `supersedes:` refs, and dual-live
   subjects render as an explicit `CONFLICT` marker in the digest — never a
   silent pick; enforcement of one-live-rule stays with t2r-06-adr-frontmatter-docs-lint's
   `aet docs lint` — M (traces: R-5)
3. [x] Digest renderer in `src/aet/context_digest.py`: stable subject-sorted
   section; each rule cites its ADR chain (live ADR + superseded lineage).
   Generated on every invocation — no committed artifact, nothing
   hand-maintained — S (traces: R-5)
4. [x] Durable-insight reader + selector interface in
   `src/aet/context_digest.py`: read `.agents/learnings.jsonl` directly
   (line-delimited JSON, malformed lines skipped, missing file yields empty),
   sorted by recency descending (`timestamp`, tolerating legacy `date`); a
   `Selector` protocol with
   `TopNRecentSelector` (default N=5) as the shipped degrade path, so the
   recurrence-threshold promotion selector plugs in later without call-site
   changes — M (traces: R-5)
5. [x] Wire both into `aet context` output (extend `src/aet/cli/context.py`
   created by t2r-04-aet-context-command): add `rules_digest` and `durable_insights` fields to
   the JSON shape and a digest section to the banner rendering; empty inputs
   (no `subject:` frontmatter yet, no learnings file) degrade to empty
   sections, never errors — S (traces: R-5)
6. [x] Tests: `tests/test_context_digest.py` (new — unit: parsing, chain
   resolution, conflict rendering, selector ordering/degradation) and
   `tests/cli/test_context.py` (created by t2r-04-aet-context-command; extended — integration:
   both fields present in `aet context` JSON and banner) — M (traces: R-5)
7. [Deferred: merge to main deferred to `aet-ship` closure] Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: the digest/insight generation has its own data sources
  (ADR frontmatter, learnings.jsonl) and test surface, distinct from
  t2r-04-aet-context-command's preamble/banner/hook-mode plumbing. Merging both would push the
  combined plan past one human-day.
- [x] Expected diff (~500 lines across src + tests) materially exceeds
  branch/PR/review overhead.
- [x] Cannot share a branch with t2r-04-aet-context-command or t2r-06-adr-frontmatter-docs-lint — both are blockers that
  must land first; sharing would invert the dependency.

## Rejected Alternatives

- **Hand-maintained current-rules doc** — rejected: R-5 requires generated,
  never hand-maintained; a hand-copied rules file is exactly the drift
  pattern the structural review documents.
- **Committed generated artifact regenerated by a hook** — rejected: leaves a
  staleness window between ADR change and regeneration; generation over 57
  ADRs is cheap, so generate at read time. (R-10's `AUTO-GENERATED` pattern
  covers the CLI reference, not rules.)
- **Extend `aet mine-learnings` with a learnings.jsonl reader now** —
  rejected: verified it scans the telemetry archive only
  (`src/aet/cli/mine_learnings.py:190`); the item-3 recurrence-threshold
  mechanism has not landed, and PRD Open Question 5's default is the top-N
  degrade path. The `Selector` protocol is the plug point.
- **Update aet-prime's `LEARNINGS` preamble line in this plan** — rejected:
  preamble absorption is t2r-05 (R-4); editing skill prose here would
  collide with that sibling's diff.
- **Emit ledger events for digest generation** — rejected: ledger kinds are
  `cut`/`stage`/`verdict`/`land` (`src/aet/ledger.py:28`); a read-only
  generation produces no state transition to provenance.

## Files to Modify

- `src/aet/context_digest.py` (new)
- `src/aet/cli/context.py` (created by t2r-04-aet-context-command; extended)
- `tests/test_context_digest.py` (new)
- `tests/cli/test_context.py` (created by t2r-04-aet-context-command; extended)

## Validation Steps

- [x] Lint passes (`make lint-py`)
- [x] Tests pass (`make test`)
- [x] `tests/test_context_digest.py` (unit): ADRs without `subject:` are
  excluded; chain resolution picks the single live rule; dual-live subjects
  render `CONFLICT`; `TopNRecentSelector` orders by recency (`timestamp`,
  tolerating legacy `date`) descending and caps at N; malformed JSONL lines
  and a missing learnings file yield empty, not errors
- [x] `tests/cli/test_context.py` (integration): `aet context` JSON contains
  `rules_digest` and `durable_insights`; the banner renders the digest
  section; both degrade to empty sections on a fixture without ADR
  frontmatter or learnings
- [x] No committed digest artifact: `git ls-files | grep -i current-rules`
  is empty — the digest exists only at runtime
- [x] R-trace coverage: R-5 covered by tasks 1–6; no task cites another R-id
- [x] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. The change is additive (one new module, one extended
command, tests); no state is written, so nothing needs unwinding.

## Pipeline

`standard` — new code path plus integration with t2r-04-aet-context-command's command; no
auth/data/dependency risk that would justify `full`.

---

*Stage: synced*
*Next step: run `aet-ship`*

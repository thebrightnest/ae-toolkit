---
id: t2r-06-adr-frontmatter-docs-lint
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: extends the docs-lint rule grammar with a new evaluator path that parses repo files
docs_sync: required
docs_sync_reason: rewrites live rule prose in two skills, one template, and the ADR corpus frontmatter
---

# Plan: ADR `subject:`/`supersedes:` Frontmatter and One-Live-Rule Docs Lint

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-9). ADR-040
(`docs/adr/040-documentation-invariants-as-data.md`) established
invariants-as-data for `aet docs lint` and states the rule grammar is a
public contract — changing it requires a new ADR. This plan therefore lands
ADR-056 alongside the grammar extension (new rule type
`unique_live_subject`).

Verified current truth on the three known contradictions (the review's cited
paths have moved — recorded here so the plan is scoped against reality):

1. **Intake-commit rules** — already textually resolved by the ADR-054/lop
   series. All four live surfaces agree ("no commit or push at intake;
   durability deferred to terminal closure"): `skills/aet-work/SKILL.md:179`,
   `skills/aet-work/references/queue-commands.md:33`,
   `skills/aet-pipeline-plan/SKILL.md:120`, `docs/WORKFLOW-github.md:36`.
   Resolution here means pinning the agreement as data so it cannot regress,
   not re-litigating it. (Review cited `.agents/reference/queue-commands.md`;
   that file now lives at `skills/aet-work/references/queue-commands.md`.)
2. **Direct-JSON-edit permission** — live. `queue-commands.md:169` permits
   "direct JSON update if the task status is unchanged" while
   `queue-commands.md:271` says always use `aet state transition`. A second,
   worse drift: `skills/aet-work/SKILL.md:65` still documents the chained
   `content_hash` tamper-evidence for the git-refs backend, but slc-01
   (ADR-055) removed it — `src/aet/backends/git_refs_backend.py:15-19` now
   stamps the envelope with `schema_version` and treats live refs as ground
   truth. The tamper-evident `content_hash` survives only in the JSON
   backend (`src/aet/queue.py:407-410,465`).
3. **Footer-format strings** — live. `skills/aet-upgrade/SKILL.md:100-106`
   emits `Next step: aet-work` while
   `skills/aet-upgrade/references/breaking-change-template.md:66-68` emits
   `Next step: aet-pipeline-implement` — a skill deleted per ADR-039's
   namespace taxonomy (CHANGELOG: "Skill removed"; the template is the only
   live doc still referencing it). The skill file is canonical.

Collision note for sequencing: R-5's current-rules digest is generated from
this same ADR frontmatter, so the R-5 plan should declare `blocked_by:
[t2r-06-adr-frontmatter-docs-lint]`; the two plans must not share a branch.

Ledger discipline: `aet docs lint` produces no task state, and the taxonomy
in `src/aet/ledger.py` (`cut`, `stage`, `verdict`, `land`) has no fitting
kind — this plan emits no ledger events and adds no prose writer around
`aet gate submit` or `aet state set-stage`.

Size re-evaluation: the >2-subsystems signal trips (src/aet code+tests,
skills/, docs/adr/, .agents/), but expected diff (~420 lines) and ≤ 1
human-day hold, so only one of three signals trips — no split; see Floor
Check.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Write ADR-056 (new file `056-adr-relations-as-frontmatter.md` under
   `docs/adr/`): extends ADR-040's
   grammar with the ADR frontmatter contract (`subject:` list, `supersedes:`
   list of ADR numbers) and the new `unique_live_subject` rule type
   (one subject, one live rule); register it in the `docs/adr/README.md`
   index — S (traces: R-9)
2. Add the frontmatter contract to `docs/adr/000-template.md`: YAML
   frontmatter block with `subject:` and `supersedes:` keys and a one-line
   statement of the one-live-rule invariant — S (traces: R-9)
3. Backfill frontmatter on the existing ADRs covering the five review-named
   subjects — state, evidence, branch model, unattended gates, metrics —
   choosing subject names granularly and recording `supersedes:` edges where
   a later ADR replaced an earlier mechanism (e.g. 055's ledger settled-ness
   supersedes 034's versioned-plan-data mechanism), so every declared
   subject resolves to exactly one live ADR and `aet docs lint` passes on
   the real corpus — M (traces: R-9)
4. Implement `unique_live_subject` in `src/aet/docs_lint.py`: extend
   `VALID_RULE_TYPES` (line 13) and the evaluator to load every `*.md`
   under the rule's target directory (excluding `000-template.md` and
   `README.md`), parse frontmatter with `yaml.safe_load` only, group by
   `subject:`, and fail when a subject has more than one ADR not named in
   another ADR's `supersedes:` — the violation message names the subject
   and all live ADR ids — M (traces: R-9)
5. Resolve contradiction 2: delete the "direct JSON update" permission at
   `skills/aet-work/references/queue-commands.md:169` (the stale-worktree
   repair goes through `aet state transition` only, matching line 271), and
   rewrite `skills/aet-work/SKILL.md:65` to the post-slc-01 truth —
   git-refs envelope is `schema_version`-stamped with live refs as ground
   truth (ADR-055); tamper-evident `content_hash` protection applies to the
   JSON backend only — S (traces: R-9)
6. Resolve contradiction 3: change
   `skills/aet-upgrade/references/breaking-change-template.md:68` from
   `Next step: aet-pipeline-implement` to `Next step: aet-work`, matching
   the canonical footer in `skills/aet-upgrade/SKILL.md:100-106` — S
   (traces: R-9)
7. Codify all three resolutions in `.agents/doc-rules.yaml`: the
   `unique_live_subject` rule targeting `docs/adr/`; `must_contain` "No
   commit or push happens at intake" on `skills/aet-work/SKILL.md` and
   `skills/aet-work/references/queue-commands.md`; `must_not_contain`
   "commit the plan files" scoped to `skills/`; `must_not_contain`
   "aet-pipeline-implement" on
   `skills/aet-upgrade/references/breaking-change-template.md`;
   `must_not_contain` "direct JSON update" on
   `skills/aet-work/references/queue-commands.md` — S (traces: R-9)
8. Add unit tests for the new rule type in
   `tests/scripts/test_docs_lint.py`: dual-live subject fails, superseded
   subject passes, ADR without frontmatter is ignored, malformed frontmatter
   fails closed with a diagnostic message, message names subject and live
   ids — S (traces: R-9)
9. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: the frontmatter contract plus one-live-rule lint plus
  the three contradiction resolutions is one independently shippable,
  reviewable behavior; nothing else in the t2r series edits these files.
- [x] Expected diff (~420 lines across src, tests, skills, ADRs, rules)
  materially exceeds branch/PR/review overhead.
- [x] Cannot share a branch with the R-5 digest plan: R-5 consumes this
  frontmatter, so it is sequenced behind this plan via `blocked_by`, not
  merged into it (two behaviors, one dependency).

## Rejected Alternatives

- **Hand-maintained current-rules doc instead of machine-checkable
  frontmatter** — rejected: a hand-maintained copy is the drift pattern R-9
  exists to kill, and R-5 generates the digest from this same data; prose
  would be a third writer.
- **Substring-only rules for the three contradictions, no subject lint** —
  rejected: pins today's three instances but leaves the defect class (one
  subject, two live rules) uncatchable, which is the point of R-9.
- **Keep the direct-JSON-update permission for status-unchanged repairs** —
  rejected: two sanctioned writers re-create the split (slc-05 precedent,
  learnings:43); `aet state transition` already covers the repair without
  status change.
- **Derive supersession from the `## Status` prose section instead of
  `supersedes:` edges** — rejected: prose status is not machine-checkable;
  the lint must derive liveness from data (ADR-040's own principle).

## Files to Modify

- `docs/adr/` — new file `056-adr-relations-as-frontmatter.md`
- `docs/adr/000-template.md`
- `docs/adr/README.md`
- `docs/adr/0*.md` — frontmatter backfill on the ADRs carrying the five
  subjects (state, evidence, branch model, unattended gates, metrics)
- `src/aet/docs_lint.py`
- `tests/scripts/test_docs_lint.py`
- `.agents/doc-rules.yaml`
- `skills/aet-work/SKILL.md`
- `skills/aet-work/references/queue-commands.md`
- `skills/aet-upgrade/references/breaking-change-template.md`

## Validation Steps

- [ ] Lint passes (`make lint-py`); full gate `make validate` green
- [ ] Tests pass (`make test`)
- [ ] `tests/scripts/test_docs_lint.py` covers `unique_live_subject` (unit,
      single layer: rules fixture + tmp ADR tree): dual-live subject fails
      naming subject and live ids; superseded subject passes; frontmatter
      parsed with `yaml.safe_load` only
- [ ] Integration (real corpus): `aet docs lint` exits 0 after the backfill,
      and exits 1 when a fixture ADR claims an already-live subject (the
      PRD's deliberately-introduced-dual-live-rule acceptance criterion)
- [ ] `grep -rn "aet-pipeline-implement" skills/ docs/adr/ .agents/` returns
      no live-surface hits; `grep -n "direct JSON update"
      skills/aet-work/references/queue-commands.md` is empty;
      `grep -n "content_hash" skills/aet-work/SKILL.md` no longer describes
      the git-refs backend
- [ ] No new source file introduced without a named test: `docs_lint.py` is
      extended in place and covered by the named `test_docs_lint.py` cases
      (no API-boundary tests — no frontend/backend contract touched)
- [ ] R-trace coverage: R-9 covered by tasks 1–8; no task cites another R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. ADR frontmatter is additive metadata, the doc-rules
entries and skill-prose resolutions restore with the revert, and no runtime
state or ledger events are produced by this plan.

## Pipeline

`standard` — default grouping; no auth, data-model, API, or dependency
surface beyond the lint evaluator itself.

---

## Divergence Summary

*Recorded: 2026-08-11 — Branch: t2r-06-adr-frontmatter-docs-lint*

### Changed from plan

- Added directory-target support for `must_contain` / `must_not_contain` rules so
  the `must_not_contain "commit the plan files" scoped to skills/` rule could be
  expressed directly. The plan described the rule as scoped to `skills/`; the
  base rule engine previously only supported file targets.

### Added (unplanned)

- None.

### Deferred

- Task 9 (merge branch to main and verify integration): deferred to the
  `aet-ship` closure stage, consistent with the standard pipeline.

---

*Stage: qa-complete*
*Next step: run `aet-review`*

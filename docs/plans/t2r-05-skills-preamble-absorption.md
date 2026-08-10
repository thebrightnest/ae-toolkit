---
id: t2r-05-skills-preamble-absorption
size: M
work_class: normal
blocked_by:
  - t2r-04-aet-context-command
pipeline: standard
security_review: skipped
security_review_reason: content-only prose edits in skills/; no code, auth, dependency, or endpoint surface in the diff
docs_sync: required
docs_sync_reason: PRD R-4 acceptance count (16 blocks + 11 banners) must be reconciled with the as-built inventory (wrapper headings, banner variant)
---

# Plan: Skills Preamble/Banner Absorption into `aet context`

## Context

PRD: `docs/prds/structural-review-tier-2-prd.md` (R-4; consumes the command
contract delivered under R-3). The structural review's incident log shows
agents half-executing 16 hand-collected prose preambles and hand-parsing
footers; R-3 (plan `t2r-04-aet-context-command`) delivers `aet context`, one command emitting
the fixed Shared Preamble fields as JSON plus a stage banner. The t2r-04-aet-context-command
contract was verified against this plan's assumptions: its emitted battery
includes `ACTIVE_PLAN` and `LAST_PIV`, and its banner format matches what
the replacement one-liner below consumes. This plan deletes the duplicated
prose and points every skill at the command.

Verified inventory (2026-08-10, against current `main`):

- 12 `## Shared Preamble` blocks: `skills/aet-prime/SKILL.md:18`,
  `skills/aet-evolve/SKILL.md:18`, `skills/aet-design-system-creation/SKILL.md:33`,
  `skills/aet-plan/SKILL.md:19`, `skills/aet-cso/SKILL.md:18`,
  `skills/aet-review/SKILL.md:17`, `skills/aet-sync-docs/SKILL.md:18`,
  `skills/aet-qa/SKILL.md:17`, `skills/aet-implement/SKILL.md:16`,
  `skills/aet-work/SKILL.md:17`, `skills/aet-verify/SKILL.md:17`,
  `skills/aet-extract-stack/SKILL.md:46`
- 4 renamed `## Before You Start` blocks with the same body:
  `skills/aet-tdd/SKILL.md:18`, `skills/aet-upgrade/SKILL.md:17`,
  `skills/aet-validate-scope/SKILL.md:28`, `skills/aet-pipeline-plan/SKILL.md:27`
- 11 stage-banner prints: aet-tdd:32, aet-implement:31, aet-validate-scope:44,
  aet-review:32, aet-work:32, aet-cso:33, aet-plan:34, aet-qa:32,
  aet-sync-docs:32, aet-extract-stack:61, and the **variant** at
  aet-pipeline-plan:42 (`"📍 Current stage: {stage} — resuming pipeline from
  the appropriate step."`).

Deviations from the PRD-level inventory, recorded for docs-sync:

- aet-plan and aet-design-system-creation carry a `## Before You Start`
  **wrapper heading** (aet-plan:17, aet-design-system-creation:31) directly
  above their `## Shared Preamble`; the wrapper goes dead when the inner
  block is replaced and must be collapsed.
- `aet context` does not exist in `src/aet/` yet — this plan is blocked
  until t2r-04-aet-context-command merges, and the replacement one-liner targets that plan's
  emitted shape (fixed battery: branch, repo state, AGENTS.md, learnings,
  active plan/PRD stage, plus banner).

Assumptions (flag at `aet-validate-scope` if t2r-04-aet-context-command's shape differs):

- `aet context` JSON covers the full fixed battery including `ACTIVE_PLAN`
  (11 of 16 blocks) and `LAST_PIV` (10 of 16 blocks) — neither is named in
  R-3's field list.
- Skill-specific fields not in the fixed battery stay in the skill as short
  retained bullets: aet-tdd `TEST_SETUP`; aet-pipeline-plan
  `EXISTING_BRIEFS`/`EXISTING_PRDS`; aet-upgrade `DEPENDENCY`,
  `CURRENT_VERSION`, `PACKAGE_MANAGER`, `SMOKE_STATUS`; aet-validate-scope
  `CONTEXT_MD`, `DOCS_ADR`; aet-extract-stack `SCAN_TARGET`, `OUTPUT_DIR`;
  aet-verify `WORK_CLASS`, `SMOKE_CMD`, `QA_REPORT_PATH`.
- aet-evolve's trigger-matched `LEARNINGS` variant (aet-evolve:25) deletes
  with the fixed battery; learnings selection moves to `aet context`
  (R-3/R-5), so no per-skill selection rule is retained.
- Skills without a preamble (aet-bug-report, aet-release-prep, aet-setup,
  aet-ship) are untouched.

No ledger events: this mechanism produces no state (pure content deletion);
nothing here writes through `aet gate submit` or `aet state set-stage`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. [x] Confirm t2r-04-aet-context-command has merged and `aet context` runs on `main`; record its
   emitted JSON field list and banner format in the task notes as the
   replacement contract. If any fixed-battery field (e.g. `LAST_PIV`,
   `ACTIVE_PLAN`) is missing from the emitted shape, stop and raise at
   scope validation rather than silently dropping the field — S
   (traces: R-4)
   - Verified contract: `aet context` emits `branch`, `repo_state`, `agents_md`,
     `learnings`, `active_plan`, `last_piv`, `active_prd_stage`, `active_plan_stage`
     and banner `"📍 Current stage: {stage}."`
2. [x] In each of the 12 `## Shared Preamble` skills (`skills/aet-prime/SKILL.md`,
   `skills/aet-evolve/SKILL.md`, `skills/aet-design-system-creation/SKILL.md`,
   `skills/aet-plan/SKILL.md`, `skills/aet-cso/SKILL.md`,
   `skills/aet-review/SKILL.md`, `skills/aet-sync-docs/SKILL.md`,
   `skills/aet-qa/SKILL.md`, `skills/aet-implement/SKILL.md`,
   `skills/aet-work/SKILL.md`, `skills/aet-verify/SKILL.md`,
   `skills/aet-extract-stack/SKILL.md`), replace the whole preamble block
   (heading, "Before executing…" line, fixed-battery bullets, "Use this
   context…" line) with one `## Context` section of this form:

   ```markdown
   ## Context

   Run `aet context` and parse its JSON for session context (branch, repo
   state, AGENTS.md, learnings, active plan/PRD stage); print the stage
   banner it emits. Do not ask the user for this context manually.
   ```

   keeping any retained skill-specific bullets (per Context assumptions) as
   short lines under the same section — M (traces: R-4)
3. [x] Apply the same replacement to the 4 `## Before You Start` skills
   (`skills/aet-tdd/SKILL.md`, `skills/aet-upgrade/SKILL.md`,
   `skills/aet-validate-scope/SKILL.md`, `skills/aet-pipeline-plan/SKILL.md`),
   and collapse the dead `## Before You Start` wrapper headings in
   `skills/aet-plan/SKILL.md:17` and
   `skills/aet-design-system-creation/SKILL.md:31` into the single
   `## Context` section — S (traces: R-4)
4. [x] Delete the 11 stage-banner print instructions, including the variant
   text at `skills/aet-pipeline-plan/SKILL.md:42` (the banner is emitted by
   `aet context`; no skill-side print remains) — S (traces: R-4)
5. [x] Sweep each edited SKILL.md for dangling references to the deleted block
   (`Shared Preamble`, `BRANCH`, `REPO_STATE`, `📍 Current stage`,
   `Before You Start`) and re-point or delete them; confirm every file
   stays under 400 lines and all relative links still resolve — S
   (traces: R-4)
6. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: this is a content-only deletion/consumption sweep in
  `skills/`; t2r-04-aet-context-command (the `aet context` command) is `src/` code with its own
  tests — different subsystem, different validation surface.
- [x] Expected diff (~290 lines: ~240 deleted across 16 files, ~50 added)
  materially exceeds branch/PR/review overhead.
- [x] Cannot share a branch with t2r-04-aet-context-command: this plan is downstream of it
  (blocked_by) and must review against a merged `aet context` contract.

## Rejected Alternatives

- **Merge into t2r-04-aet-context-command** — rejected: couples a `src/` command with tests to
  a 16-file content sweep; the content PR reviews cleanly against
  `scripts/validate-skills.sh` only after the command contract is merged.
- **Scripted rewrite (sed/codemod across all 16 files)** — rejected: six
  block variants (extra fields, two wrapper headings, one banner text
  variant) make a mechanical rewrite more error-prone than 16 hand edits;
  the grep-zero validation catches stragglers either way.
- **Keep the fixed battery in skills whose blocks have extra fields** —
  rejected: partial duplication is the drift pattern the PRD deletes; extra
  fields survive as individual retained bullets, the battery does not.
- **Retain a skill-side banner print as fallback** — rejected: two banner
  sources re-creates the writer/reader split the slc series eliminated;
  the banner is the command's output, consumed verbatim.

## Files to Modify

- `skills/aet-prime/SKILL.md`
- `skills/aet-evolve/SKILL.md`
- `skills/aet-design-system-creation/SKILL.md`
- `skills/aet-plan/SKILL.md`
- `skills/aet-cso/SKILL.md`
- `skills/aet-review/SKILL.md`
- `skills/aet-sync-docs/SKILL.md`
- `skills/aet-qa/SKILL.md`
- `skills/aet-implement/SKILL.md`
- `skills/aet-work/SKILL.md`
- `skills/aet-verify/SKILL.md`
- `skills/aet-extract-stack/SKILL.md`
- `skills/aet-tdd/SKILL.md`
- `skills/aet-upgrade/SKILL.md`
- `skills/aet-validate-scope/SKILL.md`
- `skills/aet-pipeline-plan/SKILL.md`

## Validation Steps

- [x] `scripts/validate-skills.sh` passes (structure, frontmatter, link
  resolution, 400-line limit)
- [x] `make lint` passes on the edited SKILL.md files
- [x] No new source files — no new tests required; coverage is structural
  (validator + grep-zero checks below), not unit/integration/API
- [x] `grep -rn "## Shared Preamble" skills/` returns zero matches
- [x] `grep -rn "📍 Current stage" skills/` returns zero matches
- [x] `grep -rn "Before You Start" skills/` returns zero matches
- [x] `grep -rln "aet context" skills/` lists exactly the 16 edited files
- [x] Retained skill-specific bullets survive: `grep -n "TEST_SETUP"
  skills/aet-tdd/SKILL.md`, `grep -n "SCAN_TARGET"
  skills/aet-extract-stack/SKILL.md`, `grep -n "QA_REPORT_PATH"
  skills/aet-verify/SKILL.md` each return a match
- [x] `wc -l skills/*/SKILL.md` shows every file under 400 lines
- [x] R-trace coverage: R-4 covered by tasks 1–5; no task cites another R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` (deferred to `aet-ship`)

## Rollback Plan

Revert the merge. All changes are prose deletions/replacements in skill
content; the revert restores the preamble blocks and banner prints exactly.
No state, ledger events, or code paths are touched, so nothing else needs
unwinding.

## Pipeline

`standard` per assignment and size-M default. No risk override: the diff is
content-only in `skills/`, and security review is skipped (frontmatter
reason), so the standard grouping loses no needed gate.

---

*Stage: reviewed*
*Next step: run `aet-sync-docs`*

---
id: nc-05-sync-docs-mechanical-spike
size: M
blocked_by: []
pipeline: minimal
status: merged
security_review: skipped
security_review_reason: Investigation and audit-doc output only; no code lands here.
docs_sync: skipped
docs_sync_reason: Produces a new audit doc rather than touching existing shipped documentation; the audit doc is itself the new artifact.
---

# Plan: aet-sync-docs Mechanical-Slice Spike

## Context

Source: `docs/prds/namespace-consolidation-prd.md`, R-5 + Open Question #5. Unlike R-3/R-4 (aet-ship, aet-release-prep), `aet-sync-docs` has **no existing script** — verified directly: `aet-sync-docs/` contains only `SKILL.md` (127 lines), `examples/`, and `references/`, no `bin/` or executable. R-5's text names three candidate mechanical slices inside the `sync` procedure: changed-file diffing (step 2: `git diff` for the current branch), task-list checkbox-state writing (step 6: marking `✓`/`[Changed: ...]`/`[Deferred: ...]`), and resolving the active plan/PRD pair (step 1). Step 3 (comparing plan intent vs. actual diff — classifying completed/changed/added/dropped) is explicitly named as staying skill judgment.

This ticket is a **spike**, not a build ticket: Open Question #5 ("whether R-5's mechanical slice is worth a standalone invocation at all") is explicitly "an output of the design spike," not a decision this PRD or its planning pass may presume. This ticket's only deliverable is a findings document with a go/no-go recommendation — it does not implement a subcommand and does not draft the follow-up ticket regardless of outcome.

Caution carried over from this session's own experience: `nc-03a/b/c` exist because an earlier hypothesis about `aet-ship`'s scope (assumed from memory, not verified) turned out to badly underestimate the real work once the source files were actually read. This spike's task list is deliberately empirical (task 2) rather than trusting R-5's Technical Notes at face value, for the same reason.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] N/A — no defect redirect needed

## Task List

1. Re-derive the three claimed mechanical slices directly against `aet-sync-docs/SKILL.md`'s `sync` procedure (steps 1, 2, 6) to confirm the boundary holds as literally written, distinct from the judgment step (step 3: divergence classification) — S (traces: R-5)
2. Empirically test the boundary against at least 3 historical merged plan/PRD pairs already in this repo's history (a merged `docs/plans/*.md` with a corresponding `## Divergence Summary` in its PRD): for each, manually perform steps 1, 2, and 6 as if mechanical, and confirm no judgment call was silently required to complete them — M (traces: R-5)
3. Evaluate whether the isolated mechanical slice is valuable enough to justify a standalone `aet` subcommand at all, versus remaining deterministic-but-unextracted steps inside the skill (Open Question #5): weigh session-step savings and output-consistency benefit against added CLI-surface maintenance cost — M (traces: R-5)
4. Record the naming consequence for a "go" outcome: any resulting subcommand must be named per ADR-039's noun-scoped, nested-verb convention (`nc-01`), not the flat-hyphenated `sync-docs` spelling R-5 uses illustratively — flat hyphenation is a shape ADR-039 already rejects for other renames (e.g. `queue-sync`) — S (traces: R-1, R-5)
5. Write findings to `docs/audits/nc-05-sync-docs-mechanical-findings.md`: an explicit go/no-go recommendation, the empirical evidence gathered in task 2, and — only if "go" — a one-paragraph sketch of the follow-up ticket's scope and its `blocked_by: nc-01-namespace-taxonomy-adr` dependency. Do not draft the follow-up ticket itself in this spike — M (traces: R-5)
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions.
- [x] The diff is expected to exceed 50 lines (the findings doc is substantive: boundary analysis, empirical evidence from 3 historical cases, and a recommendation).
- [x] The work cannot share a branch/PR with related tickets — it is a standalone investigation with no shared dependency on any other in-flight ticket in this PRD.

## Rejected Alternatives

- **Skipping the empirical check and trusting the PRD's Technical Notes at face value** — rejected: this session already made and caught exactly this mistake once for R-3's scope; this spike exists specifically to avoid repeating it for R-5.
- **Deciding go/no-go now, during planning, without running the spike** — rejected: explicitly deferred by the PRD's own Open Question #5 framing ("an output of the design spike").
- **Drafting the follow-up implementation ticket inside this spike regardless of outcome** — rejected: would presume the spike's own conclusion before the investigation runs.

## Files to Modify

- `docs/audits/nc-05-sync-docs-mechanical-findings.md` (new)

## Validation Steps

- [ ] Lint passes
- [ ] R-trace coverage: R-5 (and R-1's naming note) covered by tasks 1–5; no task cites an unknown R-id
- [ ] Named check per new file: `docs/audits/nc-05-sync-docs-mechanical-findings.md` — confirm the findings doc states an explicit, unambiguous go/no-go recommendation (not left open-ended)
- [ ] Test types: N/A — investigation and audit-doc output only, no executable code
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit; the findings doc un-publishes. No downstream ticket depends on it yet, since none has been drafted regardless of this spike's outcome.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | ---------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

`minimal` fits here: an investigation producing one audit document, with no code, dependency, auth, or API surface of its own.

---

*Stage: merged*
*Next step: run `aet-sync-docs`*

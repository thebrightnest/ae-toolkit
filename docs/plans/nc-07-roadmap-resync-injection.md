---
id: nc-07-roadmap-resync-injection
size: S
blocked_by: []
pipeline: minimal
status: approved
security_review: skipped
security_review_reason: Docs-only roadmap edit; no code, dependency, or config surface changes.
docs_sync: skipped
docs_sync_reason: This ticket's entire deliverable is the roadmap doc edit itself; there is no separate shipped doc left to reconcile afterward.
---

# Plan: Resync and Inject into the Package-Extraction Roadmap

## Context

Source: `docs/prds/namespace-consolidation-prd.md`, the roadmap-resync slice of R-7, and R-8. Target: `docs/roadmaps/aet-package-extraction-roadmap.md`. R-7's other two clauses — fixing `.agents/commands/aet-work.md`'s false `aet ship` claim and adding `"ship"` to the installer's legacy-prune list — are owned by `nc-03c`, not this ticket; R-7's daemonization-doc clause is owned by `nc-06`. This ticket covers only the roadmap Status Tracker resync and R-8's injection points.

Verified directly against `docs/plans/pkg-*.md` frontmatter and `git log`: `pkg-01-decision-records` is `status: merged` (commit `5a65702`, "record ADR-036/037/038 and update AGENTS.md decision log") — this **is** Phase A0's ADR set, already fully done. `pkg-02-package-skeleton` is `status: merged` (A1a, per its own commit message) — Phase A1 has started. `pkg-03` through `pkg-13` are all `status: queued` — drafted and approved, not yet implemented. The roadmap's current Status Tracker (lines 140-150) shows A0 as "pending" and A1 as "pending, Blocked by A0" — both stale.

Verified directly: Phase A1's existing bullet (lines 60-61) already names `aet-ship/bin/ship`, `aet-evolve/bin/*`, `aet-setup/bin/*`, `aet-setup/lib/harness_guard.py` but omits `aet-release-prep/release-prep.sh` and any `aet-sync-docs` script entirely — confirming R-8's claimed gap exactly. Verified: the Typer-consolidation item (candidate for the taxonomy-ADR cross-reference) lives in **Phase A4** (line 102-103: "Typer (or Click) consolidates the 19 argparse binaries"), not Phase A1 — `pkg-11-typer-consolidation.md`'s own `blocked_by: [pkg-06-cross-skill-extraction]` places it downstream of Phase A1, consistent with the roadmap's own Phase A4 placement.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] N/A — no defect redirect needed

## Task List

1. Resync the Status Tracker table (lines 140-150): flip Phase A0 to done/Accepted (pkg-01 merged; ADR-036/037/038 recorded) and drop A1's now-satisfied "Blocked by A0" annotation, flipping A1 to "In Progress" (pkg-02/A1a merged; pkg-03 through pkg-06 queued, not yet implemented); leave A2/A3/A4 (still blocked by A1, not yet started) and A5 (independent) unchanged — S (traces: R-7)
2. Add a cross-reference to the taxonomy ADR (ADR-039, produced by `nc-01`) on Phase A4's Typer-consolidation bullet (line 102-103), noting it must land before pkg-11's implementation since pkg-11 now carries the CLI rename spec (`nc-02`) — S (traces: R-1, R-8)
3. Amend Phase A1's existing bullet covering `aet-ship/bin/ship`, `aet-evolve/bin/*`, `aet-setup/bin/*` (lines 60-61) to also name `aet-release-prep/release-prep.sh` (promoted into the package, not relocated as bash — see `nc-04`) and, conditionally, aet-sync-docs' mechanical slice ("if `nc-05`'s spike concludes it is separable") — closing the pre-existing gap where the bullet omitted both — S (traces: R-4, R-5, R-8)
4. Add a note to Phase A1's `aet-work/bin/*` → `aet/cli/*` bullet (lines 58-59) associating the orchestrator/status daemonization work (`nc-06`) with this relocation, referenced against pkg-04 specifically — not pkg-06 — S (traces: R-6, R-8)
5. Tighten Phase A1's "Done when" line (lines 67-68) from "no Python file remains inside any skill directory" to "no Python file or executable script remains inside any skill directory" — consistent with R-4's stricter acceptance criterion (no executable script remaining at the skill root, not merely no Python file) — S (traces: R-4, R-8)
6. Confirm Phase A4's bullet list (lines 100-104) still describes dependency adoption only, with no namespace-consolidation content beyond the ADR-039 cross-reference added in task 2 — S (traces: R-8)
7. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions.
- [x] The diff is expected to exceed 50 lines across the Status Tracker table and four separate Phase A1/A4 edits, even though confined to one file.
- [x] The work cannot share a branch/PR with other tickets — it is a standalone doc resync with no shared dependency on any other in-flight ticket.

## Rejected Alternatives

- **Also fixing `.agents/commands/aet-work.md` and the legacy-prune list here** — rejected: those are R-7 clauses already owned by `nc-03c` (ship section, `LEGACY_NAMES`) and `nc-06` (run/run-one section); duplicating them here would create two tickets editing the same lines.
- **Injecting the ship/release-prep/sync-docs promotions into Phase A4** — rejected: R-8 explicitly requires Phase A4 to keep describing dependency adoption only; these promotions belong in Phase A1, where the actual relocation work happens.
- **Leaving the Status Tracker's stale "pending"/"Blocked by A0" entries for a future pass** — rejected: this PRD's own Overview names documentation drift as the root problem being fixed; leaving a known-stale tracker uncorrected while fixing the same failure mode elsewhere would be inconsistent.

## Files to Modify

- `docs/roadmaps/aet-package-extraction-roadmap.md`

## Validation Steps

- [ ] Lint passes
- [ ] R-trace coverage: R-7 (roadmap slice) and R-8 covered by tasks 1–6; R-1, R-4, R-5, R-6 cross-references noted where relevant; no task cites an unknown R-id
- [ ] Named check per new file: N/A — no new file is introduced; the roadmap is amended in place
- [ ] Test types: N/A — plan-document edit only, no executable code
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit amending the roadmap; the Status Tracker and Phase A1/A4 bullets revert to their pre-amendment (stale) state. No code or other plan files are affected.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | ---------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

`minimal` fits here: a contained plan-document edit with no code, dependency, auth, or API surface of its own.

---

*Stage: plan-approved*
*Next step: run `aet-work`*

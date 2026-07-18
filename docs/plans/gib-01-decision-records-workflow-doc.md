---
id: gib-01-decision-records-workflow-doc
size: M
blocked_by: []
pipeline: minimal
status: draft
security_review: skipped
security_review_reason: authors ADRs, a workflow doc, and a roadmap edit under docs/; no runtime code, no trust boundary, no dependency surface. Pure decision record.
docs_sync: skipped
docs_sync_reason: this task *is* the documentation change (ADRs + workflow + roadmap); there is no separate skill/code contract to sync it against.
---

# Plan: Decision Records + Engineer-Facing Workflow Doc

## Context

- PRD: `docs/prds/github-issues-backlog-projection-prd.md` (R-18).
- Everything downstream cites these records. Cheap and first, mirroring the `rdm-01` pattern for Phase 0.
- Grounded in doc 09 (`content/fable-review/09-2026-07-10-roadmap.md`) and doc 10 (`10-2026-07-12-two-mode-reframe.md`).

⚠️ VALIDATE ACK: scope — ADRs 032/033/034 are authored by this plan (task 1); their paths are forward-declarations of files this plan creates, not references to existing decisions. Same pattern as rdm-01, which created 020/021.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **New ADR (supersede ADR-014):** "GitHub Issues is a projection, not a backend." Records that `task_backend: "github"` never stored in GitHub (load/save hit local JSON), that projections are an axis orthogonal to storage, and that no config may make a forge authoritative.
- **New ADR:** "Projections fail open; storage fails closed." Records the one sanctioned inversion of the fail-closed kernel rule, scoped to the projection dispatcher.
- **New ADR:** "Settled-ness is derived from versioned plan data." Resolves the ADR-013 decision-3 vs `init-queue:257` contradiction — closure is read from committed plan `status`, never from the gitignored history log.
- **Workflow doc** (`docs/WORKFLOW-github.md` or a section in `docs/CONVENTIONS.md`): the engineer-facing `aet add → promote → aet run → ship` loop, stating that AET is the only writer to GitHub and the one human act is promotion.
- **Roadmap edit:** in doc 09, move Phase 6 into Phase 9 (triggered expansion) with its triggers recorded (a live shared-ledger need; server-side enforcement demand); renumber references. Note the replacement by this PRD.

## Rejected Alternatives

- **Fold all three ADRs into one** — rejected: they supersede different prior decisions (ADR-014 vs ADR-013) and will be cited independently; separate records keep the trace clean.
- **Skip the workflow doc, rely on skill prose** — rejected: the owner explicitly asked for a workflow engineers follow (scope boundary); an undocumented convention is exactly what erodes.
- **Delete Phase 6 from the roadmap** — rejected: it is trigger-gated, not wrong; the greenfield precedent (ADR-021) is to shelve with triggers, not erase.

## Task List

1. Write the three ADRs (`docs/adr/032`, `033`, `034`) — M (traces: R-18)
2. Write the engineer-facing GitHub workflow doc — S (traces: R-18)
3. Edit roadmap doc 09: Phase 6 → Phase 9 with triggers; update phase summary table + cross-refs — S (traces: R-18)
4. Update `docs/adr/README.md` index and ADR-014 status line (superseded-by) — S (traces: R-18)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Near-identical additions (three ADRs + doc) that share one branch — correctly batched
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot meaningfully split without fragmenting one decision set

## Files to Modify

- `docs/adr/032-github-issues-projection-not-backend.md` (new)
- `docs/adr/033-projections-fail-open-storage-fail-closed.md` (new)
- `docs/adr/034-settled-from-versioned-plan-data.md` (new)
- `docs/WORKFLOW-github.md` (new) or `docs/CONVENTIONS.md`
- `docs/adr/014-optional-github-issues-adapter.md` (status line), `docs/adr/README.md`
- `content/fable-review/09-2026-07-10-roadmap.md`

## Validation Steps

- [ ] `make lint` passes (markdownlint)
- [ ] Each ADR follows `docs/adr/000-template.md` structure (Status, Context, Decision, Consequences)
- [ ] ADR-014 carries a "Superseded by ADR-032" line; README index lists all three
- [ ] Roadmap phase table and every "Phase 6/7/8" cross-reference are internally consistent after renumber
- [ ] R-trace coverage: R-18 covered by tasks 1–4; no unknown R-ids
- [ ] No named test (docs-only task); coverage is the lint + structural checks above

## Rollback Plan

Revert the merge commit. No runtime effect; ADR-014 returns to Accepted, roadmap returns to prior numbering.

## Pipeline

`pipeline: minimal` — docs-only, no isolation benefit from stage grouping.

---

_Stage: reviewed_

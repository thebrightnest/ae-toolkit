---
id: pkg-01-decision-records
size: S
blocked_by: []
pipeline: minimal
status: approved
security_review: skipped
security_review_reason: Docs-only ADRs; no code, dependency, or config surface changes.
docs_sync: skipped
docs_sync_reason: The diff is itself the decision documentation; there is no code divergence to sync.
---

# Plan: Decision Records for Package Extraction (A0)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-1).
Roadmap phase A0. Three stale decisions must be formally superseded before any
code moves: "markdown-only repo" and "runtime code has no Python dependencies"
(`AGENTS.md` decision log), and ADR-016's "not changing the directory layout"
caveat. Additionally, merged PRD `roadmap-p2-aet-binary-prd.md` declared "no
merging of binaries into one Python program; exec dispatch only" — the layout
ADR must explicitly reverse that stance.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Write `036-repo-is-content-plus-python-package.md` under `docs/adr/` — supersedes
   "markdown-only repo"; records src layout (`src/aet/`, `skills/`, `tests/`,
   `scripts/`) and that the tool is a versioned Python package — S (traces: R-1)
2. Write `037-runtime-dependency-policy.md` under `docs/adr/` — supersedes "no runtime
   dependencies"; principle: stdlib for glue, dependencies for formats,
   protocols, and UI; each new dependency gets its own plan + security review
   (vgr-04 precedent) — S (traces: R-1)
3. Write `038-directory-layout-change.md` under `docs/adr/` — amends ADR-016's layout
   caveat; explicitly reverses roadmap-p2's "no merging of binaries into one
   Python program" non-goal; records that skills become pure content under
   `skills/` — S (traces: R-1)
4. Update `AGENTS.md` decision log: replace the two stale entries with pointers
   to ADR-036/037/038 — S (traces: R-1)
5. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] Three ADRs batched into one plan deliberately: they are one decision
  bundle reviewed together, each file small; splitting would triple gate
  overhead for zero added signal.

## Rejected Alternatives

- **One combined ADR** — rejected: the three decisions have independent
  audiences and lifetimes; separate ADRs let Track B supersede only the
  dependency policy's distribution implications later.
- **Edit ADR-016 in place** — rejected: ADRs are immutable once accepted;
  amendment happens by new ADR referencing the old.

## Files to Modify

- `036-repo-is-content-plus-python-package.md` under `docs/adr/` (new)
- `037-runtime-dependency-policy.md` under `docs/adr/` (new)
- `038-directory-layout-change.md` under `docs/adr/` (new)
- `AGENTS.md` (decision log section only)

## Validation Steps

- [ ] `make validate` passes (docs-only change)
- [ ] Each ADR names the decision it supersedes/amends and its Status section
  links the superseded artifact
- [ ] `AGENTS.md` decision log no longer contains the strings "Markdown-only
  repo" or "no requirements.txt" as active decisions
- [ ] R-trace coverage: R-1 covered by tasks 1–4; no unknown R-ids cited
- [ ] No new source files introduced (docs-only) — test coverage requirement n/a
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; ADR files are additive and `AGENTS.md` is a single
section edit — `git revert` restores the prior state cleanly.

---

*Stage: plan-approved*
*Next step: run `aet-work`*

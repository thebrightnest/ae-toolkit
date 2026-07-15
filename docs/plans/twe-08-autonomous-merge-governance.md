---
id: twe-08-autonomous-merge-governance
size: S
blocked_by:
  - ewl-06-adversarial-rehearsal
pipeline: standard
security_review: required
security_review_reason: this plan defines the autonomous-merge must-stop boundary in governance and scrubs the self-merge ambiguity from aet-ship. The wording must close the gap the 2026-07-15 audit exploited, not re-open it — mis-scoped or ambiguous governance here silently re-enables the bypass, so the review verifies the boundary is stated fail-closed and unambiguous.
docs_sync: skipped
docs_sync_reason: the deliverable IS the governance documentation (the ADR-005 extension's CONVENTIONS mirror + aet-ship skill wording); there is no separate code change for aet-sync-docs to reconcile docs against.
status: approved
---

# Plan: Autonomous-Merge Governance — ADR-005 Extension Mirror + `aet-ship` Merge-Neutral Hygiene

## Context

- PRD: `docs/prds/roadmap-p4-two-human-ends-prd.md` (G5; R-12). Remediates the **2026-07-15 autonomous-shipping audit** (`docs/audits/2026-07-15-autonomous-shipping-audit.md`).
- The **governance half** of G5: state the autonomous-merge boundary in code-adjacent governance (not load-bearing prose an AI reinterprets), and remove the in-skill ambiguity the incident exploited.
- **Ground truth (2026-07-15):** `docs/adr/005-execution-mode.md` lists three "Gates That Must Still Stop in Unattended Mode" (ATOMIC OVERSIZED, Critical/High security, merge-verification failures), mirrored in `docs/CONVENTIONS.md` (§ "Gates That Must Still Stop in Unattended Mode", currently three bullets). `ADR-027` set the precedent for **extending** ADR-005 with a new must-stop category via a **new** ADR (ADRs are immutable). `aet-ship/SKILL.md:199` (step 14) says closure runs "after the PR is created and **the user indicates it has been merged**", but its Key Principles (`:285`) say "**Non-interactive by default** — the gate runs without human input until something is wrong" — the exact self-contradiction the agent resolved into a self-merge.
- **The ADR itself is authored at `aet-validate-scope`** (ADR candidate 3 in the PRD), so this plan **mirrors** the already-authored ADR into `CONVENTIONS.md` and does the skill hygiene; it does not write the ADR.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (net-new governance boundary), not a reproducible defect. The audit's one reproducible defect (gap-1 closure-push) is split to `aet-bug-report`.

## Locked design

- **`docs/CONVENTIONS.md`** — add a fourth bullet to "Gates That Must Still Stop in Unattended Mode": **autonomous merge** (an agent issuing a PR merge / `gh pr merge`) is fail-closed even in unattended mode, citing the new ADR. Mirror the ADR's wording exactly (one enforcement source of truth).
- **`aet-ship/SKILL.md`** — make the skill **merge-neutral**:
  - Step 14: state the human-merge boundary unambiguously (the PR merge is the human's decision; the skill's job begins at post-merge closure verification).
  - Reconcile the "Non-interactive by default … without human input until something is wrong" Key Principle so it scopes to the *validation gate*, not the *merge action* — it must not read as license to self-merge.
  - Confirm (grep) the skill instructs **no** `gh pr merge` anywhere.
- **Author checklist** in `CONVENTIONS.md` (§ "Author Checklist") — add "autonomous-merge is fail-closed; skills never instruct a PR merge" so the boundary is enforced on future skill edits.

## Rejected Alternatives

- **Edit ADR-005 in place** — rejected: ADRs are immutable once accepted; a new ADR extends it (ADR-027 precedent). (The new ADR is authored at validate-scope; this plan mirrors it.)
- **Encode the boundary only in `AGENTS.md` prose (the audit's A/B/C)** — rejected: prose an AI reinterprets is the load-bearing-markdown defect the toolkit is systematically removing (ADR-020 razor: a self-merge skips a gate → code/governance, not prose).
- **Leave `aet-ship`'s wording as-is and rely on the guard alone** — rejected: the guard (twe-09) is the mechanism, but the skill's self-contradiction is the ambiguity that authorized the leap; both the mechanism and the instruction must be closed.

## Task List

1. Mirror the new ADR's autonomous-merge must-stop category into `docs/CONVENTIONS.md` (gate list + Author Checklist) — S (traces: R-12)
2. `aet-ship/SKILL.md` merge-neutral hygiene: unambiguous human-merge boundary in step 14, scoped Key Principle, no `gh pr merge` — S (traces: R-12)
3. Add `tests/test_merge_governance.py` asserting the governance is present and the ambiguity is gone — S (traces: R-12, R-14)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level (governance mirror + skill hygiene are one coherent boundary-statement)
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Independent of `twe-09` (governance docs vs. setup code) — both implement the audit remediation and run in parallel worktrees

## Files to Modify

- `docs/CONVENTIONS.md`
- `aet-ship/SKILL.md`
- `tests/test_merge_governance.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_merge_governance.py`:
  - `test_conventions_lists_autonomous_merge_must_stop` (asserts the fourth must-stop bullet is present and references the ADR)
  - `test_aet_ship_states_human_merge_boundary` (asserts step 14's human-merge wording is present)
  - `test_aet_ship_has_no_self_merge_instruction` (asserts no `gh pr merge` / self-merge directive in the skill)
- [ ] R-trace coverage: R-12 by tasks 1–2; R-14 (governance slice) by task 3; no unknown R-ids cited
- [ ] The new ADR (authored at validate-scope) exists and is referenced by the CONVENTIONS mirror
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The governance text and skill wording return to their prior form; the twe-09 guard (if merged) still stands on its own. No state migration.

## Pipeline

`pipeline: standard` with `security_review: required` — the review stage scrutinizes that the boundary wording is fail-closed and unambiguous (the audit's failure was ambiguity, so the wording is the security surface).

---

*Stage: plan-approved*
*Next step: run `aet-work`*

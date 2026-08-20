---
blocked_by:
docs_sync: required
id: trp-01-post-intake-consumer-audit
pipeline: standard
security_review: skipped
size: S
work_class: normal
---

# Plan: Enumerate Every Post-Intake Plan-File Consumer

## Context

- PRD: `docs/prds/the-record-is-the-plan-prd.md` (R-1)
- R-19: `docs/prds/open-work-board-prd.md:47`; glossary at :163
- Decision: ADR-061 (the record is the plan after intake)

Three consumers are known — the ship family, R-5's archive, `metrics._declared_size`.
All three were found by tracing a symptom backwards, which is not a search
strategy. This plan looks for the rest before the siblings assume the list is
complete.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The defects it registers are already filed; this produces the register

## Task List

1. [x] Enumerate every read of `plan_file`, `plans_dir`, `docs/plans`, and
   `resolve_plan_arg` across `src/`, and classify each as authoring-phase
   (correct) or post-intake (stale) — S (traces: R-1)
2. [x] For each post-intake consumer, name its replacement spec field
   (`spec.frontmatter`, `spec.tasks`, `spec.title`, `spec.body`) or record that
   no field carries the data — S (traces: R-1)
3. [x] Extend the sweep beyond the package: `panel/`, `reports/`, `scripts/`, and
   any consumer of `docs/plans/archive/` — S (traces: R-1)
4. [x] Record the register in the PRD's Technical Notes, and state explicitly
   whether the sibling plans' scope is complete or must grow — S (traces: R-1)
5. [ ] Merge branch to main and verify integration — S (deferred to `aet-ship` after `synced`; pipeline session ends at `qa-complete`)

## Floor Check

- [ ] Expected diff is below the calibrated floor threshold (≤ 50 headline lines)
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against
- [x] This is docs-only and its sole consumer is a single sibling

One box, and `plans lint` fires it: `trp-06` is the only sibling that declares
`blocked_by` on this plan. An earlier draft of this section claimed all five
siblings consume the register; that was not true of the declared graph, and the
lint was right to contradict it.

One signal is a prompt to justify, not to merge. The justification: merging this
into `trp-06` would place the search *after* `trp-02`, since `trp-06` is blocked
on it. The audit exists to tell us whether `trp-02`'s scope is complete, so
running it afterwards inverts the order and answers the question too late to act
on. The register is small; the sequencing is the reason it is separate.

The expected diff is not below the floor threshold: the sweep covers `src/`,
`panel/`, `reports/`, `scripts/` and the skills tree, and the register names
every consumer with file, line and replacement field.

## Rejected Alternatives

- **Skip the audit; fix the three known consumers** — rejected: all three were
  found by tracing symptoms, and each failed silently for weeks. The absence of a
  fourth symptom is not evidence of a fourth consumer's absence (ADR-059).
- **Fold the register into `trp-06`'s skill audit** — rejected: `trp-06` corrects
  prose, this searches code. Different corpora, and `trp-06` is blocked on this.

## Files to Modify

- `docs/prds/the-record-is-the-plan-prd.md`

## Validation Steps

- [x] Lint passes (`make lint`, `aet plans lint`, `aet docs lint`)
- [x] R-trace coverage: R-1 covered by tasks 1-4
- [x] The register names every consumer with its file, line, and replacement field
- [x] The sweep covers the repository, not only `src/aet/`
- [x] A written statement of whether sibling scope is complete
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` — deferred to `aet-ship` after `synced`

## Rollback Plan

Revert the commit. The register is prose; removing it changes no behaviour.

## Pipeline

`standard`.

---

*Stage: synced*
*Next step: run `aet-ship`*

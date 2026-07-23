---
id: psr-02-record-delivered-size
size: M
blocked_by: []
pipeline: standard
status: queued
security_review: required
security_review_reason: introduces subprocess git invocation with interpolated branch and commit refs on the closure path
docs_sync: required
docs_sync_reason: adds a new recorded field to work-history.jsonl, which is a documented local data surface
---

# Plan: Record delivered diff size at task closure

## Context

- PRD: `docs/prds/plan-sizing-recalibration-prd.md` (R-7, R-8)
- ADR: `docs/adr/046-plan-size-measured-not-gated.md` — authored during scope
  validation; this plan is the measurement half of that decision
- Related: ADR-015 (telemetry informs guardrails, local-first)

Plan-time size gating was retired because plan-time diff size is unknowable. This
plan collects the real number at the one moment it is knowable — task closure,
when the branch and merge commit are both settled — and records it against the
size label the plan declared.

This plan is **not blocked by `psr-01`**. It touches disjoint files (runtime
closure path vs. docs/skills/validator) and delivers value independently: it
starts accumulating calibration data regardless of whether the bands have been
recalibrated yet. The ADR it references is documentation of an already-approved
decision, not a technical dependency.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Locked design

- **The measurement is exact, not heuristic.** The evidence in the PRD was
  gathered by matching commit subjects to plan ids, which is approximate. The
  production path does not need that: the task record already carries
  `merge_commit`.
- **Measure the first-parent range, not a merge base against trunk.** The
  delivered diff is `git diff <merge_commit>^1..<merge_commit>`. This is both
  simpler and more correct than a merge-base computation:
  - For a **squash** merge, the squash commit's first parent *is* the trunk tip
    at merge time, so the range is exactly what the task contributed.
  - For a **regular** merge commit, `^1` is the trunk side and `^2` the branch,
    so the range is precisely what the branch brought in.
  - It needs no trunk ref, no configuration, and is unaffected by trunk having
    advanced since the merge.
  Measured over the existing history: 267 of 289 records (92%) carry a
  `merge_commit`, versus only 167 (58%) carrying a `branch` — so the
  commit-anchored range also survives branch pruning, which a branch-anchored
  one does not.
- **Reuse the existing ref resolution.** `src/aet/cli/aet_state.py:76`
  `resolve_merge_commit(branch, cwd)` already exists and
  `src/aet/track_record.py:386` already derives merge commits from git. Do not
  add a third way to resolve a merge commit.
- **No dependency on the branch resolver.** `src/aet/branch_ref.py` does not
  exist yet — it is created by `epi-01-base-branch-resolver`, which is queued
  under a different PRD. The first-parent range removes any need for it, so this
  plan carries no cross-PRD blocker.
- **Two numbers, not one.** Record the headline diff (excluding `docs/`,
  `.agents/`, `content/`, `reports/`) and the total, so the planning-artifact
  share stays visible. The headline is what the bands are defined against.
- **Recording never fails closure.** If the diff cannot be computed — pruned
  branch, missing merge commit, git error — record the reason and continue. A
  telemetry field must not be able to block a task from settling.
- **Refs are passed as argv, never interpolated into a shell string.** All git
  invocations use list-form `subprocess` with no `shell=True`.

## Task List

1. Add `src/aet/plan_size.py` with `delivered_size(repo_root, merge_commit)`
   returning headline lines, total lines, and a status/reason, computed over the
   first-parent range using list-form subprocess — M (traces: R-7)
2. Classify each changed path as planning-artifact or implementation using the
   same exclusion set the PRD's bands are defined against, exposed as a named
   constant rather than an inline literal — S (traces: R-7)
3. Record the result on the task's history entry in
   `src/aet/queue.py::append_history_record`, alongside the plan's declared
   `size` label so the pair is comparable per task — M (traces: R-7, R-8)
4. Call the measurement from the closure path in
   `src/aet/cli/orchestrator.py::_finalize_task`, wrapped so any failure degrades
   to a recorded reason and never blocks settling — S (traces: R-7)
5. Add `tests/test_plan_size.py` covering the computation, the exclusion split,
   and each degradation path — M (traces: R-7)
6. Extend the history-record tests to pin that the new fields are written and
   that a failed measurement still settles the task — S (traces: R-7, R-8)
7. Merge branch to main and verify integration — S

**Size definitions (as proposed by this PRD, dogfooded here):**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 600 lines — re-evaluate against the full model; justify above 1500

Expected diff ≈ 400–500 lines across one new module, two touched call sites, and
two test files. **M** under the proposed bands.

### Floor Check

- [x] Stands alone: after this lands, every newly closed task records what it
      actually delivered, which is useful with no further work
- [x] Diff materially exceeds branch/PR/review overhead
- [x] Cannot be usefully merged with `psr-03`: backfill and reporting are
      consumers of the schema this plan defines, and splitting them keeps this
      plan's review focused on the closure path where the risk is

## Rejected Alternatives

- **Compute the diff at plan time from files-to-modify** — rejected: this is the
  proxy trap ADR-046 closes. The number is only real after implementation.
- **Attribute diffs by matching commit subjects to plan ids** — rejected: that is
  the approximate method used for the PRD's evidence gathering. The task record
  already holds `merge_commit`, so exactness is free.
- **Compute a merge base against the configured trunk ref** — rejected: it would
  block this plan on `epi-01-base-branch-resolver` (queued, different PRD) for no
  gain, and it is less accurate than the first-parent range once trunk has moved
  on since the merge.
- **Anchor the measurement on the task's `branch`** — rejected: only 58% of
  existing history records carry a branch, and branches are pruned after merge,
  so backfill in `psr-03` would lose most of the corpus.
- **Add a new frontmatter field for a size estimate** — rejected: the existing
  `size` label already is the declared estimate; a second field would need
  reconciling with it.
- **Block closure when the diff wildly exceeds the declared label** — rejected:
  that reintroduces gating, just later. This plan collects evidence; it does not
  judge. Any enforcement decision belongs to a future PRD informed by the data.
- **Write to a new dedicated ledger file** — rejected: `work-history.jsonl` is
  the established append-only settled-task record and already carries `branch`,
  `merge_commit`, and `cost`. A parallel file would fragment the record.

## Files to Modify

- `src/aet/plan_size.py` (new)
- `src/aet/queue.py`
- `src/aet/cli/orchestrator.py`
- `tests/test_plan_size.py` (new)
- `tests/` — existing history-record test module (extend)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] `make validate` passes
- [ ] New source coverage: `src/aet/plan_size.py` is covered by
      `tests/test_plan_size.py`, which names cases for (a) a squash merge whose
      first-parent range yields the expected headline and total, (b) a regular
      merge commit where `^1` is the trunk side, (c) the planning-artifact
      exclusion split, (d) a missing `merge_commit`, (e) a commit with no parent
      (root commit), and (f) a git invocation returning non-zero
- [ ] Test types: `tests/test_plan_size.py` is unit-level against a temporary git
      fixture repo; the history-record extension is an integration test across
      the closure path and the queue writer. No API boundary surface is touched.
- [ ] A task whose measurement fails still reaches its settled state, with the
      failure reason recorded rather than raised
- [ ] No `shell=True` and no f-string interpolation of refs into a command string
      anywhere in the new module
- [ ] No reference to a trunk branch, `main`, or `src/aet/branch_ref.py` is
      introduced; the measurement is anchored solely on `merge_commit`
- [ ] R-trace coverage: R-7 by tasks 1,2,3,4,5,6; R-8 by tasks 3,6. R-9 and R-10
      are carried by `psr-03`; R-1 … R-6 and R-11 … R-17 by `psr-01`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The new fields are additive on an append-only record, so
existing consumers ignore them and no migration is needed. Records written before
the revert remain valid and are simply not extended by later closures.

## Pipeline

`standard`.

---

*Stage: secure*
*Next step: run `aet-sync-docs`, then `aet-ship`*

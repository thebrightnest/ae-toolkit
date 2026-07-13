---
id: pfe-01-verdict-freshness-primitive
size: M
blocked_by: []
pipeline: standard
status: approved
security_review: skipped
security_review_reason: additive local primitive — hashes the repo's own worktree through a throwaway git index and reads already-trusted verdict JSON; no untrusted-input parsing, no network, no new trust boundary
docs_sync: required
docs_sync_reason: the verdict schema gains a required tree_hash field and a freshness vocabulary (run/lint-only/skip); the structured-gate-evidence contract (ADR-019) and docs/telemetry-guide.md must record it
---

# Plan: Verdict Tree-Hash Provenance & Validation-Freshness Primitive

## Context

- **Driving brief:** `docs/audits/2026-07-13-pipeline-flow-efficiency.md` — finding
  **F2** ("Validation runs are not deduplicated": the full suite ran 4–5× per
  task against trees that between stages often changed only a markdown footer)
  and recommendation **R2** ("Validation freshness rule — tree-hash diff since
  last green; docs-only → lint/format only").
- This plan is the **atom**: a content fingerprint of the working tree, stamped
  onto every verdict as provenance, plus a freshness query that reads it. The
  behavior change that consumes it is `pfe-02` (orchestrator injection).
- **Divergence from the audit, deliberate:** R2's "Where it lives" column
  imagined skill-text edits (aet-qa/review/cso). We implement it in code
  instead — a skill cannot be trusted to _remember_ to check freshness, and the
  decision must be code-enforced (see the determinism principle recorded for
  this toolkit). The skill-text alternative is rejected below.
- **Second payoff:** the same `tree_hash` — "which git object this evidence
  attests to" — is the atom the roadmap's Phase 3 ancestry-closure gate needs
  (`content/fable-review/09`). This plan adds the field once; closure reuses it.
- **Implementation status — committed, verify-and-upgrade:** the implementation
  is committed on branch `pfe-01-verdict-freshness-primitive`
  (`aet-work/lib/verifier.py`, `aet-work/lib/evidence.py`,
  `tests/test_validation_freshness.py`, `tests/test_gate_evidence.py`); full
  suite green (606), ruff clean. **This plan does not rebuild from scratch.** Its
  job is to confirm the committed code matches the Locked design and R2 intent,
  run it through the review/CSO/sync gates, and apply only the Upgrade
  candidates below that prove worthwhile. Re-deriving what already exists is the
  exact waste (F1) this audit condemns.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Locked design

- **`verifier.working_tree_hash(worktree_dir) -> str`.** Stage every tracked and
  untracked-not-ignored path into a throwaway `GIT_INDEX_FILE` (`git add -A`),
  then `git write-tree`. Captures uncommitted mid-stage state; the tree object
  persists in the real object store so it stays diffable later. Returns `""` on
  any failure (non-git dir, git absent) → callers treat empty as "revalidate."
  The real index is never touched.
- **`verifier.changed_paths(worktree_dir, tree_a, tree_b) -> list[str] | None`.**
  `git diff --name-only` between two tree ids; `None` when it cannot be computed
  (missing tree) → "unknown, revalidate," never "nothing changed."
- **`tree_hash` on the verdict schema.** Add `"tree_hash": str` to all four
  verdict kinds (qa/review/cso/sync-docs). `write_verdict` stamps it from the
  worktree _before_ validation when the caller omitted it — the code stamps
  provenance, the skill contract is unchanged. Required field: every
  contract-written verdict names its tree (the invariant closure will rely on).
- **`evidence.validation_freshness(task_id, kind, worktree_dir, ...) ->
FreshnessResult`.** Compares the worktree hash to the last verdict's
  `tree_hash`: no prior / prior fail / unknown hash → `RUN`; identical → `SKIP`;
  only non-code changed → `LINT_ONLY`; any code changed or undiffable → `RUN`.
  `default_is_code_path` treats only `docs/`, `*.md`, and the learnings log as
  non-code. Bias is always toward `RUN`.

## Upgrade candidates

Checked during the verify pass; apply only where clearly worthwhile, else record
as a follow-up.

- **Warm-cache hashing** — seed the scratch index from the real index (not only
  `HEAD`) so `git add -A` re-hashes only changed paths on large trees.
- **Configurable code-path classifier** — let a project override
  `default_is_code_path` (config / workflow file) so non-Python repos tune what
  counts as non-code.
- **`test_run` provenance** — stamp `tree_hash` on the `test_run` telemetry
  record too, so runs correlate to trees (overlaps the ttf line).
- **Closure reuse** — expose `tree_hash` for the Phase 3 ancestry-closure gate
  (the second payoff named in Context).

## Rejected Alternatives

- **Implement R2 as skill-text (the audit's suggested location)** — rejected:
  a freshness rule expressed as prose asks the agent to _remember_ to check and
  to _reason_ about staleness, re-creating the AI-discretion failure the rule
  exists to remove. The decision belongs in code; skills obey it.
- **`tree_hash` as an optional field** — rejected: optional provenance is
  weaker evidence and gives the future closure gate nothing to rely on. A
  required field auto-stamped by the one write path costs only a one-line update
  to the direct-`validate_verdict` tests (clean cut, no back-compat shim).
- **Key freshness on the commit hash (`HEAD`)** — rejected: misses uncommitted
  mid-stage edits, which are exactly the state a stage validates. A working-tree
  tree object is the honest content fingerprint.
- **Path→test impact mapping instead of a tree diff** — rejected: aet-qa already
  does impact-scoping; it answers "which tests cover these files," not "has
  anything changed since the last green." Freshness answers the second, which is
  what F2's repeat runs need. The two compose; this does not replace impact scope.

## Task List

Implementation is committed (branch `pfe-validation-freshness`). Execute these as
**verification** — confirm each unit is present and matches the Locked design —
applying only the Upgrade candidates that prove worthwhile. Do not re-implement
what exists.

1. Verify `verifier.py`: `working_tree_hash` + `changed_paths` (defensive;
   empty/None on failure) — S (traces: R2)
2. `evidence.py`: `tree_hash` on the four schemas; `write_verdict` auto-stamp;
   `validation_freshness` + `FreshnessResult` + `default_is_code_path` — M
   (traces: R2)
3. `tests/test_validation_freshness.py` (new): real temp-repo coverage of the
   hash (stable / content-sensitive / uncommitted / non-git), `changed_paths`,
   the code-path classifier, and every freshness branch (no prior, unchanged,
   docs-only, code, mixed, prior-fail, missing-hash) — M (traces: R2)
4. `tests/test_gate_evidence.py`: add `tree_hash` to the direct verdict records;
   assert `write_verdict` stamps it and does not mutate the caller's dict — S
   (traces: R2)
5. Docs: record the `tree_hash` field + freshness vocabulary against the
   evidence contract (ADR-019 note / `docs/telemetry-guide.md`) — S (traces: R2)
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks — `pfe-02` consumes
      this and is blocked on it; merging the two would exceed L.

## Files to Modify

- `aet-work/lib/verifier.py`
- `aet-work/lib/evidence.py`
- `tests/test_validation_freshness.py` (new — covers the primitive)
- `tests/test_gate_evidence.py`
- ADR-019 / `docs/telemetry-guide.md` (schema + vocabulary note)

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`python3 -m pytest tests/test_validation_freshness.py tests/test_gate_evidence.py tests/test_verifier.py -q`, then full suite before commit)
- [ ] Named coverage: `tests/test_validation_freshness.py` covers the new
      `verifier` primitives and `evidence.validation_freshness`; the
      `write_verdict` auto-stamp is asserted in `tests/test_gate_evidence.py`
- [ ] Distinguish test types: unit (hash, classifier, freshness branches) exercised against real temp git repos
- [ ] R-trace coverage: R2 covered; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. `tree_hash` stops being written; `validation_freshness`
becomes dead code with no caller (until `pfe-02`). Existing verdicts on disk are
regenerated each run, so no data migration is involved. If reconciling the
pre-existing spike: either commit the working-tree changes as this plan's
implementation, or `git checkout` them and let `aet run` rebuild from the plan.

## Pipeline

`standard` — touches the gate-evidence contract; keep the review pass even
though there is no security surface (security_review skipped with reason).

---

_Stage: plan-approved_
_Next step: run `aet-work`_

---
id: pfe-02-orchestrator-freshness-injection
size: S
blocked_by:
  - pfe-01-verdict-freshness-primitive
pipeline: standard
status: merged
security_review: required
docs_sync: skipped
docs_sync_reason: orchestrator-internal prompt modulation; the injected clause and the AET_QA_FRESHNESS signal are runtime behavior, not a documented contract — no user-facing doc changes
---

# Plan: Orchestrator QA-Freshness Prompt Injection

## Context

- **Driving brief:** `docs/audits/2026-07-13-pipeline-flow-efficiency.md` — F2
  and R2 (see `pfe-01`). This plan is the **behavior change** that banks the
  saving: it makes downstream checking stages stop re-running the full suite on
  a tree QA already proved green.
- **Depends on `pfe-01`** for `evidence.validation_freshness` and the `tree_hash`
  stamped on the QA verdict.
- **Why the orchestrator, not the skills:** the instruction that _causes_ the
  repeat runs — "Run validations (tests, lint, format checks) in the foreground"
  — is injected by the orchestrator into every stage prompt
  (`build_prompt` / `build_stage_group_prompt`), not written in the skill files.
  Modulating it at that single source keeps one instruction owner (no prose
  drift), and the orchestrator knows the real worktree path — a stage session
  would misresolve it (`AET_REPO_ROOT` can point at the main repo, not the
  worktree). The decision is computed in code and handed to the stage as a fact.
- **Anchor is the QA verdict:** QA is the stage that runs `make validate`;
  review/cso/sync re-ran it only as belt-and-suspenders. Freshness is always
  computed against the `qa` verdict.
- **Implementation status — committed, verify-and-upgrade:** the implementation
  is committed on branch `pfe-02-orchestrator-freshness-injection`
  (`aet-work/bin/orchestrator`, `tests/test_orchestrator.py`); full suite green
  (606), ruff clean, and a live demo confirms the injected clause across
  fresh / changed / docs-only trees. **This plan does not rebuild from scratch:**
  confirm the committed code matches the Locked design and R2 intent, run it
  through the gates, and apply only the Upgrade candidates below.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Locked design

- `_qa_freshness_decision(task_id, repo_root, worktree_dir) -> str` — calls
  `evidence.validation_freshness(task_id, "qa", ...)` with the slug derived from
  `repo_root`; returns the decision or `""`. Never raises: a stage spawn must not
  hinge on this optimization (`except (OSError, ValueError)` → `""`).
- `_freshness_clause(decision) -> str` — empty for `RUN`/unknown; for `SKIP`,
  "trust the QA verdict and do NOT re-run the test suite"; for `LINT_ONLY`,
  "run lint/format checks only." Both carry the guard: "if you modify code,
  re-run full validation before finishing" (covers the case where the stage
  edits the tree after spawn).
- `build_prompt` and `build_stage_group_prompt` take an optional
  `freshness_clause` (default `""`) appended to the validations sentence — the
  builders stay pure (no IO); the orchestrator computes the clause and passes it.
- `run_stage` and `run_stage_group` compute the decision before building the
  prompt and export `AET_QA_FRESHNESS` into the stage env (observability + a hook
  for future consumers). Pre-QA spawns see no QA verdict → `RUN` → no change.

## Upgrade candidates

Checked during the verify pass; apply only where clearly worthwhile, else record
as a follow-up.

- **Exact verdict-path injection** — pass the QA verdict _path_ into the stage
  env (as with `AET_EVIDENCE_PATH_QA`) so freshness reads the exact file the
  orchestrator gated on, instead of re-deriving it from the slug.
- **Decision telemetry** — record the freshness decision (skip/lint-only/run)
  so `mine-learnings` can measure how often the dedup fires and quantify the F2
  saving (ties into the ttf measurement line).
- **Interactive parity** — the non-orchestrated `/aet-review` path gets no
  freshness; add a skill-side helper if parity is wanted.
- **Intra-group re-evaluation** — for a group session that edits the tree
  mid-way, re-evaluate freshness per stage rather than once at spawn (today the
  prose guard covers this).

## Rejected Alternatives

- **Skill-side check (aet-review/cso call `validation_freshness` themselves)** —
  rejected: the worktree would be resolved inside the session, where
  `AET_REPO_ROOT` may point at the main repo, not the worktree; and it scatters
  the "run validations" instruction across the orchestrator prompt _and_ skill
  prose (two owners, drift). The orchestrator already owns and injects that
  instruction.
- **Compute freshness once and inject a stage env var only (no prompt clause)**
  — rejected: the env var alone changes nothing unless a skill is also told to
  read it; the prompt clause is the acting instruction. The env var is kept only
  as an observability signal.
- **Gate the computation to only post-QA stages via workflow ordering** —
  rejected as needless: a pre-QA spawn finds no QA verdict and returns `RUN`
  (empty clause), so always-compute is correct and simpler; the cost is one cheap
  worktree hash per spawn.

## Task List

Implementation is committed (branch `pfe-validation-freshness`). Execute these as
**verification** — confirm each unit matches the Locked design — applying only
the Upgrade candidates that prove worthwhile. Do not re-implement what exists.

1. ✓ Verify `orchestrator`: `_qa_freshness_decision` + `_freshness_clause`; thread
   `freshness_clause` through `build_prompt` and `build_stage_group_prompt`;
   compute + inject in `run_stage` and `run_stage_group` (incl. `AET_QA_FRESHNESS`)
   — S (traces: R2)
2. ✓ `tests/test_orchestrator.py`: clause mapping; `_qa_freshness_decision` returns
   `""` without a task id and never raises on bad paths; integration — a fresh
   QA verdict injects the SKIP clause + `AET_QA_FRESHNESS=skip`, a changed tree
   omits it — S (traces: R2)
3. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions (templates, examples, docs).
- [ ] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks — `blocked_by pfe-01`;
      same concern, different layer (consuming the primitive), and merging would
      push `pfe-01` past L.

## Files to Modify

- `aet-work/bin/orchestrator`
- `tests/test_orchestrator.py`

## Validation Steps

- [x] Lint passes (`make lint-py`)
- [x] Tests pass (`python3 -m pytest tests/test_orchestrator.py -q`, then full suite before commit)
- [x] Named coverage: `TestQaFreshnessInjection` covers the clause mapping and
      the fresh/changed injection paths through `run_stage`
- [x] Distinguish test types: unit (clause mapping, defensive decision) + integration (real temp repo + QA verdict through `run_stage`, spawn stubbed)
- [x] R-trace coverage: R2 covered; no unknown R-ids cited
- [x] Behavioral check: the injected prompt carries the freshness clause when the tree is unchanged since QA and omits it after a code edit
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Stages return to the unmodulated "run validations in the
foreground" prompt — the pre-change behavior. No data or schema involved.
`pfe-01`'s primitive remains, unused by the orchestrator until re-applied.

## Pipeline

`standard` — this stage can suppress a validation re-run, so keep both the review
and CSO passes (security_review required) even though the injected text is static.

---

_Stage: merged_
_Next step: run `aet-sync-docs`, then `aet-ship`_

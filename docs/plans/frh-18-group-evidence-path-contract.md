---
id: frh-18-group-evidence-path-contract
size: M
blocked_by: []
pipeline: standard
status: approved
security_review: not-required
security_review_reason: no new trust boundary — verdict paths stay derived from the main repo root; only the env-var delivery mechanism changes
docs_sync: required
docs_sync_reason: the writer contract in four checking skills (aet-qa, aet-review, aet-cso, aet-sync-docs) is rewritten, plus ADR-023 amends the ADR-019 evidence contract
---

# Plan: Group-Session Evidence Path Contract

## Context

- On 2026-07-11 `thp-04-retention-prune-cli` was marked `failed` three times by the batch orchestrator despite complete, verified work (footer `synced`, passing cso/sync-docs verdicts, 23/23 tests). Learning in `.agents/learnings.jsonl`.
- **Root cause (confirmed by artifacts):** `run_stage` sets `AET_EVIDENCE_PATH` to the gate-canonical verdict path (`aet-work/bin/orchestrator:413-420`), but `run_stage_group` sets no evidence path at all (`aet-work/bin/orchestrator:469-475`). A group-session agent therefore falls back to the skill's default rule, whose `{project-slug}` is undefined — agents that hand-compute it from the worktree CWD write to `~/.aet/reports/<main-dir>/<worktree>/<task>/<kind>.json`, while the fail-closed gate `_load_checking_verdict` reads `derive_project_slug(repo_root)` = `<main-dir>/main`. Verdict exists, gate cannot see it → `❌ Gate fail-closed: missing cso verdict` → task failed. The same session's plan footer still advances, so re-runs reproduce the failure indefinitely.
- The bug is **nondeterministic**: agents that use `evidence.write_verdict` with defaults land on the gate path (it resolves `AET_REPO_ROOT`, which batch children inherit → main repo → `…/main` slug). 4 of 5 tasks in the same batch passed this way; thp-04's agent improvised. An implicit contract with two viable interpretations is the defect.
- The suspected second bug (stage write-back failing under batch concurrency) is **not supported by evidence**: `aet-state set-stage` holds the cross-process `queue_lock` for the full load-modify-save (`aet-work/bin/aet-state:354`), and all three thp-04 failures are fully explained by the path mismatch. No write-back hardening in this plan; the improved gate diagnostics below will expose it if it ever occurs.
- Recovery already applied manually (verdicts copied to the gate path, task promoted). This plan removes the divergence at the source.

## Intake Triage

- [x] Confirmed this is a **reproducible defect**, not a feature — reproduced twice (`failed → ready` re-runs) with identical gate failure before the manual verdict copy

## Locked design

- **Canonical resolver** in `aet-work/lib/evidence.py`: `resolve_verdict_path(task_id, kind, project_slug=None) -> Path` with precedence:
  1. `$AET_EVIDENCE_PATH` (single-stage sessions; unchanged behavior)
  2. `$AET_EVIDENCE_PATH_<KIND>` — kind uppercased, non-alphanumeric → `_` (e.g. `sync-docs` → `AET_EVIDENCE_PATH_SYNC_DOCS`)
  3. Default: `evidence_path(task_id, kind, project_slug)` (today's fallback)
- **Group sessions publish per-kind paths**: `run_stage_group` sets `AET_EVIDENCE_PATH_<KIND>` for every evidence-bound stage in the runnable span, computed with the identical formula `run_stage` uses (`evidence.evidence_path(task_id, kind, project_slug=derive_project_slug(repo_root))`). Writers and the gate now share one derivation regardless of session shape.
- **Writer contract update** in the four checking skills (`aet-qa/SKILL.md`, `aet-review/SKILL.md`, `aet-cso/SKILL.md`, `aet-sync-docs/SKILL.md`): replace the two-step path rule with the three-step precedence above, naming `resolve_verdict_path` as the canonical helper when `aet-work/lib` is importable. Keep the "write verdict before footer update" ordering.
- **Gate diagnostics**: the `missing {kind} verdict` message in `_require_passing_verdict` includes the resolved path it read, so future mismatches are a one-line diagnosis instead of a multi-hour trace.
- **ADR-023** in `docs/adr/`: amends the ADR-019 structured-gate-evidence contract — one canonical verdict location per (task, kind), delivered to writers explicitly in every session shape; improvised slug computation by agents is out of contract.

## Rejected Alternatives

- **Dual-read gate fallback** (gate also reads the worktree-slug path) — rejected: entrenches two write locations and weakens the fail-closed design; recovery from legacy paths is a one-line `cp`, as demonstrated.
- **Write-back hardening for `_record_stage`** (retry/reconcile on set-stage failure) — rejected: unproven hypothesis; `queue_lock` already serializes cross-process mutations, and the observed failures need no second cause. Revisit only if the improved diagnostics catch a real occurrence.
- **One verdict manifest file per group session** (`AET_EVIDENCE_MANIFEST` JSON) — rejected: more machinery than the per-kind env vars for at most three kinds (`qa`, `review`, `cso`, `sync-docs`); env vars match the existing single-stage contract.

## Task List

1. Add `resolve_verdict_path()` to `aet-work/lib/evidence.py` with the three-step precedence — S (traces: root cause)
2. Publish `AET_EVIDENCE_PATH_<KIND>` per evidence-bound stage in `run_stage_group`; include the resolved path in the gate's missing-verdict message — S (traces: root cause)
3. Rewrite the writer contract in the four checking skills to the three-step precedence naming `resolve_verdict_path` — S (traces: docs_sync)
4. Tests in `tests/test_gate_evidence.py`: resolver precedence (env single, env per-kind, default), group-session env contains per-kind paths equal to the gate path, gate message includes path — M (traces: root cause)
5. Add ADR-023 amending the ADR-019 evidence contract — S (traces: docs_sync)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition
- [x] Diff ~150 lines / 8 files

---

_Stage: reviewed_
_Next step: run `aet-sync-docs`_

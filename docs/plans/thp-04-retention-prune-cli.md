---
id: thp-04-retention-prune-cli
size: M
blocked_by:
  - thp-02-worktree-project-slug
pipeline: standard
status: approved
security_review: required
security_review_reason: recursive deletion inside the user's home directory — verify containment under the archive root, active-run protection, and that dry-run truly performs no writes
docs_sync: required
docs_sync_reason: guide's "Privacy and retention" section replaces the manual snippet with the CLI and records the never-prune-active rule
---

# Plan: Retention Prune CLI with Active-Run Protection

## Context

- PRD: `docs/prds/telemetry-hygiene-plan-panel-prd.md` (R-4)
- Retention today is a manual doc snippet. On 2026-07-11 that snippet's empty-dir sweep deleted the **active** run dir of a live `aet-work run` (wfd-03): run bookkeeping crashed and the task DAG stalled (learning in `.agents/learnings.jsonl`). Rule going forward: never prune the active run.
- Mechanism lands in `aet-work/lib/telemetry.py` + `aet-work/bin/report` (today's surface: `aet-work report`). The queued cli-01..05 arc renames the surface to `aet report` — write user-facing docs/help text to match whatever surface exists at implementation time; the bin+lib mechanism survives the rename either way.
- Lease: `.agents/work-queue.lease` sidecar, `read_lease()` at `aet-work/lib/queue.py:125`; orchestrator children inherit `AET_RUN_ID`.
- Archive layouts to handle (both live in the real archive): current `{project}/{date}/{run-id}/`, legacy `{project}/{date}-{run-id}/`.
- `blocked_by` thp-02: both plans edit `telemetry.py` and the guide; serialized to avoid cross-worktree merge conflicts.
- Scope boundary (PRD non-goal): prune covers the telemetry archive only — the gate-evidence reports tree (`~/.aet/reports`) is out of scope.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect (the wfd-03 deletion was caused by the _manual snippet_, which this plan retires; the learning is already recorded)

## Locked design

- **Lib**: `prune_archive(days, root=None, force=False, protected_run_ids=frozenset()) -> dict` in `telemetry.py`:
  - `cutoff = now - days`. Candidate run dir = leaf dir matching either layout where **both** the dir-name date segment parses `< cutoff` **and** the newest recursive mtime `< cutoff`. The double condition is the fix for the wfd-03 incident class: a live run's dir (even empty or summary-less) always has a fresh mtime and survives.
  - Skip any dir whose run-id segment (or contained `run_summary.run_id`) ∈ `protected_run_ids`.
  - Stale-empty sweep: after run-dir removal, delete empty `{date}`/`{project}` dirs whose mtime `< cutoff` — never fresh ones.
  - `force=False` (default) deletes nothing; returns report `{candidates: [...], deleted: [...], kept_protected: [...], bytes_reclaimed}`.
  - Whole-archive scope by default; `root` narrows to one project subtree.
- **CLI** (`aet-work/bin/report`): add `--prune DAYS` (int) and `--force`. With `--prune`: build `protected_run_ids` from `read_lease(".agents/work-queue.json")` when cwd is a repo with a lease, plus `AET_RUN_ID` if set; print the report (dry-run banner without `--force`). `--project` composes as scope. Existing report flags unchanged.
- **Docs**: replace "Retention is manual" bullet and the interim prune snippet (present in the guide version landed by P-0) with the CLI, the dry-run-first workflow, and the never-prune-active rule.

## Rejected Alternatives

- **Name-date-only cutoff (the old snippet's rule)** — rejected: it is exactly what deleted the live wfd-03 dir; mtime must gate every deletion, including empty-dir sweeps.
- **Standalone `aet-work prune` bin** — rejected: README roadmap decided `report --prune`; a new entry point would also collide with the cli-\* dispatcher sweep mid-flight.
- **Auto-prune on run start** — rejected: destructive side effects hidden inside unrelated invocations; retention stays an explicit owner action.

## Task List

1. Implement `prune_archive()` in `aet-work/lib/telemetry.py` per Locked design — M (traces: R-4)
2. Wire `--prune` / `--force` into `aet-work/bin/report` incl. lease/`AET_RUN_ID` protection assembly — S (traces: R-4)
3. Add the five named tests to `tests/test_telemetry_archive.py` + CLI smoke test (below) — M (traces: R-4)
4. Rewrite `docs/telemetry-guide.md` "Privacy and retention" around the CLI; delete the manual snippet — S (traces: R-4)
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition
- [x] Diff ~220 lines / 4 files
- [x] Cannot share a branch with thp-02 (blocked on its `telemetry.py` merge) or thp-03 (independent operational script; batching would exceed M)

## Files to Modify

- `aet-work/lib/telemetry.py`
- `aet-work/bin/report`
- `tests/test_telemetry_archive.py`
- `docs/telemetry-guide.md`

## Validation Steps

- [ ] `tests/test_telemetry_archive.py::test_prune_dry_run_lists_only` — integration: tmp archive with old+new runs; default call deletes nothing, report names only the old ones
- [ ] `tests/test_telemetry_archive.py::test_prune_force_deletes_old_runs` — integration: `force=True` removes old run dirs (both layouts) and reports bytes reclaimed; recent runs intact
- [ ] `tests/test_telemetry_archive.py::test_prune_skips_leased_run` — integration: run id in `protected_run_ids` survives a forced prune even when older than cutoff
- [ ] `tests/test_telemetry_archive.py::test_prune_skips_fresh_or_summaryless_dirs` — integration: old-dated dir with fresh mtime (the wfd-03 shape: empty/no `last-run.json`) survives
- [ ] `tests/test_telemetry_archive.py::test_prune_removes_stale_empty_dirs` — integration: empty date/project dirs older than cutoff go; fresh empty dirs stay
- [ ] `tests/test_telemetry_archive.py::test_report_prune_cli_dry_run_smoke` — API boundary: `subprocess` run of the report bin with `--prune 7` exits 0 against a tmp archive (smoke/exit-code per 2026-07-06 learning)
- [ ] R-trace coverage: R-4 by tasks 1–4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — flags and lib function disappear; the guide re-documents manual deletion. Already-pruned dirs are gone by design (dry-run-first is the operator safeguard).

---

_Stage: qa-complete_
_Next step: run `aet-review`_

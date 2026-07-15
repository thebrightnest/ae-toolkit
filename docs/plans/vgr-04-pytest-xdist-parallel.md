---
id: vgr-04-pytest-xdist-parallel
size: M
blocked_by:
  - vgr-01-slim-markdown-gates
  - vgr-02-gate-docs-adr
pipeline: standard
status: draft
security_review: required
security_review_reason: Introduces the repo's first third-party test dependency (pytest-xdist) into an otherwise dependency-free project — supply-chain and trust review of the new dev dependency.
docs_sync: required
docs_sync_reason: Changes the repo's dependency stance; AGENTS.md's "no requirements.txt" statement and a dev-install step must be updated to match.
---

# Plan: Parallelize the pytest Suite with `pytest-xdist`

## Context

PRD: [validate-gate-review](../prds/validate-gate-review-prd.md). Satisfies **R-6**
(pytest runs `-n auto`, all green deterministically, dev-dep declared, wall time
materially reduced).

pytest is 91.75s — 75% of `make validate` (610 tests + 34 subtests). The slowest
are subprocess/git-bound (`test_orchestrator` process-group kills,
`test_git_refs_parity` setup), which parallelize well. **Constraint:** this repo has
_no_ Python dependency manifest and `AGENTS.md:102` states "no requirements.txt."
Blocked by vgr-01 (shared `Makefile`) and vgr-02 (shared `AGENTS.md`).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (performance), not a defect

## Locked Architecture Decisions

- Declare `pytest-xdist` in a new minimal `requirements-dev.txt` (dev-only; does **not** reintroduce a runtime manifest).
- `make test` uses `-n auto` but **degrades gracefully to single-process** if xdist is absent, so contributors who skipped the dev install are not hard-blocked.
- Revise `AGENTS.md`'s dependency stance to "no _runtime_ deps; dev/test deps in `requirements-dev.txt`."

## Task List

1. Add `requirements-dev.txt` declaring `pytest-xdist`; update `AGENTS.md` dependency-stance line + a `pip install -r requirements-dev.txt` note — S (traces: R-6)
2. Measure parallel-safety: run `python3 -m pytest tests/ -n auto`, capture the failing/flaky set (git/process-group/tmp/cwd/env sharing are the risks) — S (traces: R-6)
3. Fix the parallel-unsafe tests from task 2 (isolate shared state via `tmp_path`/`monkeypatch`/unique dirs). **Contingency:** if the fix exceeds the session limit (≤ 8 files / ≤ 300 lines), split per auto-split with `Split from: vgr-04-pytest-xdist-parallel` — M (traces: R-6)
4. Wire `-n auto` into the `Makefile` `test` target with a single-process fallback when xdist is unavailable — S (traces: R-6)
5. Verify (see Validation Steps) and merge — S (traces: R-6)

**Size labels:** known-bounded core (t1/t2/t4/t5) is M; the isolation-fix (t3) is size-contingent on the task-2 measurement and may force an implement-time split. Overall **M** with that contingency; re-label if task 2 surfaces broad fallout.

## Batching Check

- [x] Not near-identical additions
- [x] Diff > 3 files / 50 lines
- [x] Depends on vgr-01/vgr-02 landing first (shared files)

## Rejected Alternatives

- **`pyproject.toml [project.optional-dependencies]`** — rejected for now: introduces a build-system manifest where none exists; `requirements-dev.txt` is lighter. (May be reopened at scope validation.)
- **Hard-require xdist in `make test`** — rejected: breaks contributors who have not installed dev deps; graceful single-process fallback preferred.
- **Defer xdist** — considered; owner chose include-now for the ~60s win. The fail-fast reorder (vgr-01) already mitigates the common case.

## Files to Modify

- `requirements-dev.txt` (new)
- `AGENTS.md`
- `Makefile`
- `tests/` — isolation fixes (count determined by task 2), possibly `tests/conftest.py`

## Validation Steps

- [ ] `make validate` runs pytest with `-n auto`; all 610+ tests green across workers on **two consecutive runs** (stability, not luck)
- [ ] Single-process fallback works: with `pytest-xdist` uninstalled, `make test` still runs and passes
- [ ] pytest wall time on `make validate` is materially reduced (record before/after)
- [ ] `AGENTS.md` describes the dev-dep + install; no stale "no requirements.txt" claim
- [ ] **No new source module** — the parallelized existing suite passing deterministically is the verification; isolation edits are themselves tests
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

**Self-consistency lint:** Check 1 PASS · Check 2 (requirements-dev.txt=t1, AGENTS.md=t1, Makefile=t4, tests=t3) PASS · Check 3 (observable: green across workers + timing) PASS · Check 4 (R-6 covered) PASS · Note: task-3 size WARN (contingent on task-2 measurement; auto-split path documented).

## Rollback Plan

Remove `requirements-dev.txt`, revert the `Makefile` `-n auto` line, revert test-isolation edits. Single-process pytest is unaffected throughout.

## Pipeline

`standard` — new dependency + broad test changes; per template guidance dependency changes use `standard`/`full`.

---

_Stage: reviewed_
_Next step: run `aet-cso`_

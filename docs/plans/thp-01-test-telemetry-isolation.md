---
id: thp-01-test-telemetry-isolation
size: S
blocked_by: []
pipeline: standard
status: merged
security_review: skipped
security_review_reason: test-infrastructure-only change (pytest fixture + guard test); no runtime or production code path is touched
docs_sync: required
docs_sync_reason: telemetry guide troubleshooting table gains the "junk projects in archive" row and the pollution explanation moves from panel README quirks to documented-and-fixed
---

# Plan: Test Telemetry Isolation — Stop Archive Pollution at the Source

## Context

- PRD: `docs/prds/telemetry-hygiene-plan-panel-prd.md` (R-1)
- The pytest suite spawns the real orchestrator ~160 times per run; only 4 spawn sites set `AET_TELEMETRY_ARCHIVE_DIR`, so the rest write junk projects (`tests`, `demo/project`, `tmp*`, `T/tmp*`) into the real `~/.aet/telemetry`. Env vars are inherited by every subprocess spawn, so one autouse fixture covers all call sites at once.
- `tests/conftest.py` today is only a `sys.path` insert — the fixture is greenfield.
- Explicit per-test overrides that must keep winning: `tests/test_orchestrator.py:93,103,2448,2534`, `tests/test_aet_retro_telemetry.py:72`, and `tests/test_telemetry_archive.py:46-52` (unittest-style direct `os.environ` set in `setUp` / pop in `tearDown`).

## Intake Triage

- [x] Defect-shaped but fully diagnosed (panel README, learning recorded); planned as hardening per owner direction — classification documented in the PRD's Intake Triage section.

## Locked design

- **Function-scoped autouse fixture** in `tests/conftest.py` using `monkeypatch` + `tmp_path`:

  ```python
  @pytest.fixture(autouse=True)
  def _isolate_telemetry_archive(monkeypatch, tmp_path):
      monkeypatch.setenv("AET_TELEMETRY_ARCHIVE_DIR", str(tmp_path / "telemetry-archive"))
  ```

- Why function-scoped + monkeypatch (not session-scoped `os.environ`): `test_telemetry_archive.py` pops the var in `tearDown`; monkeypatch teardown runs after and re-restores per test, so no later test falls back to the real archive. Autouse fixtures also wrap unittest.TestCase methods, and `setUp`'s explicit value wins within those tests.
- Subprocess coverage: spawns with `env=None` inherit `os.environ`; spawns that build `env` from `os.environ.copy()` pick up the fixture value; the 4 explicit sites override it — all three paths land in a temp dir.
- **Guard test** `tests/test_telemetry_isolation.py`: proves the default path is isolated without needing to touch the real archive.

## Rejected Alternatives

- **Patching each of the ~160 spawn sites** — rejected: the whole point of the env-inheritance fixture is covering every site at once; per-site edits regress on the next new test.
- **Session-scoped fixture setting `os.environ` once** — rejected: `test_telemetry_archive.py`'s `tearDown` pop would leave the rest of the session writing to the real archive.
- **One-time cleanup of existing junk dirs in this plan** — rejected: retention (thp-04) ages them out; mixing live-archive deletion into a test-only change widens the blast radius for no gain.

## Task List

1. ✓ Add the autouse `_isolate_telemetry_archive` fixture to `tests/conftest.py` — S (traces: R-1) [Changed: also patches `telemetry.DEFAULT_ARCHIVE_DIR` — tests running in-process under `patch.dict(os.environ, ..., clear=True)` wipe the env var and would otherwise fall back to the real archive]
2. ✓ Add `tests/test_telemetry_isolation.py` with the two named guard tests (below) — S (traces: R-1) [Changed: third guard test added — `test_runlogger_stays_isolated_when_env_is_cleared` proves the clear=True escape is closed]
3. ✓ Update `docs/telemetry-guide.md`: troubleshooting row for junk projects; note that suite runs are isolated by default and how a test opts out (explicit env) — S (traces: R-1)
4. Merge branch to main and verify integration — S [Deferred: merge happens at `aet-ship`]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff ≤ 3 files / ~70 lines but the change is complete on its own — nothing adjacent to batch with (thp-02+ touch different layers and are blocked on review sequencing)
- [x] Cannot share a branch: this must merge **first** to stop ongoing pollution while the rest of the arc is still in flight

## Files to Modify

- `tests/conftest.py`
- `tests/test_telemetry_isolation.py` (new)
- `docs/telemetry-guide.md`

## Validation Steps

- [ ] `tests/test_telemetry_isolation.py::test_default_env_points_into_pytest_tmp` — unit: the var is set and its value is under the pytest tmp root, not under `Path.home() / ".aet"`
- [ ] `tests/test_telemetry_isolation.py::test_runlogger_defaults_under_isolated_archive` — integration: `RunLogger(repo_root=tmp_repo)` with no explicit env creates its run dir under the fixture archive, and `Path.home()/".aet"/"telemetry"` gains no new entries
- [ ] Full suite green: `python3 -m pytest tests/`
- [ ] Manual sentinel (QA stage): `ls -R ~/.aet/telemetry` snapshot before/after a full suite run is identical
- [ ] R-trace coverage: R-1 by tasks 1–3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — removes fixture, guard test, and doc row in one step; no data or schema is touched.

---

_Stage: merged_
_Next step: run `aet-work`_

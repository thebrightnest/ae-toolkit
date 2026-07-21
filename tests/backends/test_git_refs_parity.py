"""Parity suite: JSON backend vs git-refs backend.

Runs the same ``aet-state`` scenario against two otherwise-identical scratch
repositories — one configured with ``task_backend: json`` and one with
``task_backend: git-refs`` — and asserts that the observable outcomes (live
states, transition history, and the settled JSONL record) are equivalent.

This is the behavioral safety net for the backend-routed sealing refactor:
``aet-state`` must produce the same result regardless of which backend stores
the live queue. Timestamps (``at``, ``settled_at``, ``merged_at``,
``completed_at``) are the only tolerated difference and are stripped before
comparison.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"
_spec = importlib.util.spec_from_loader(
    "aet_state_parity",
    importlib.machinery.SourceFileLoader("aet_state_parity", str(_AET_STATE_PY)),
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)

BRANCH = "feat-blocker"

# Fields that legitimately differ between runs (wall-clock timestamps).
_TIME_FIELDS = {"at", "settled_at", "merged_at", "completed_at"}


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _init_merged_repo(path: Path, branch: str = BRANCH) -> Path:
    """A repo with ``origin/main`` and a feature branch already merged into it.

    After the fast-forward merge, ``branch`` and ``origin/main`` point at the
    same commit, so ``aet-state`` accepts the ``awaiting_merge -> merged``
    transition for a task whose ``branch`` is ``branch``.
    """
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / ".agents").mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("# parity\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "initial")
    _git(path, "branch", "-M", "main")
    _git(path, "checkout", "-q", "-b", branch)
    (path / "feature.txt").write_text("feature work\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "feature")
    _git(path, "checkout", "-q", "main")
    _git(path, "merge", "-q", "--no-edit", branch)
    _git(path, "remote", "add", "origin", str(path))
    _git(path, "update-ref", "refs/remotes/origin/main", "refs/heads/main")
    return path


def _write_config(repo: Path, backend: str) -> None:
    (repo / ".agents" / "aet-work.json").write_text(
        json.dumps({"task_backend": backend}), encoding="utf-8"
    )


def _strip_times(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _strip_times(v) for k, v in value.items() if k not in _TIME_FIELDS
        }
    if isinstance(value, list):
        return [_strip_times(v) for v in value]
    return value


def _by_id(tasks: list[dict]) -> dict[str, dict]:
    return {t["id"]: _strip_times(t) for t in tasks}


def _transition(queue_file: str, task_id: str, frm: str, to: str) -> None:
    args = aet_state.argparse.Namespace(
        command="transition",
        task_id=task_id,
        from_stage=frm,
        to_stage=to,
        queue=queue_file,
        dry_run=False,
        reason=None,
    )
    rc = aet_state.cmd_transition(args)
    assert rc == 0, f"transition {task_id} {frm} -> {to} failed (rc={rc})"


def _set_stage(queue_file: str, task_id: str, stage: str) -> None:
    args = aet_state.argparse.Namespace(
        command="set-stage",
        task_id=task_id,
        stage=stage,
        queue=queue_file,
        dry_run=False,
    )
    rc = aet_state.cmd_set_stage(args)
    assert rc == 0, f"set-stage {task_id} -> {stage} failed (rc={rc})"


def _run_scenario(repo: Path, backend: str) -> dict[str, dict]:
    """Seed a blocker/dependent pair and drive the full lifecycle to merged.

    Returns a normalized snapshot: ``{"live": {id: task}, "settled": {id: task}}``.
    """
    _write_config(repo, backend)
    queue_file = str(repo / ".agents" / "work-queue.json")
    history_file = str(repo / ".agents" / "work-history.jsonl")

    blocker = {
        "id": "blocker",
        "state": "planned",
        "branch": BRANCH,
        "blocks": ["dependent"],
        "title": "Blocker task",
    }
    dependent = {
        "id": "dependent",
        "state": "blocked",
        "blocked_by": ["blocker"],
        "pending_blockers": 1,
        "title": "Dependent task",
    }

    seed_backend = aet_state.make_backend(queue_file)
    seed_backend.save([blocker, dependent])

    # Full recorded-forward chain on the blocker.
    _transition(queue_file, "blocker", "planned", "ready")
    _transition(queue_file, "blocker", "ready", "in_progress")
    _set_stage(queue_file, "blocker", "implemented")
    _transition(queue_file, "blocker", "in_progress", "awaiting_merge")
    _transition(queue_file, "blocker", "awaiting_merge", "merged")

    data = aet_state.make_backend(queue_file).load()
    settled: list[dict] = []
    if os.path.exists(history_file):
        with open(history_file, encoding="utf-8") as f:
            settled = [json.loads(line) for line in f if line.strip()]

    return {"live": _by_id(data["queue"]), "settled": _by_id(settled)}


@pytest.fixture(scope="module")
def snapshots(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict]:
    """Run the scenario for both backends and return both snapshots.

    Module-scoped: the scenario shells out to real ``git`` to build two repos,
    and every test only reads the resulting snapshot, so one run serves the
    whole file.
    """
    results: dict[str, dict] = {}
    base = tmp_path_factory.mktemp("parity")
    with pytest.MonkeyPatch.context() as mp:
        for backend in ("json", "git-refs"):
            repo = _init_merged_repo(base / backend)
            mp.chdir(repo)
            results[backend] = _run_scenario(repo, backend)
    return results


def test_transition_chain_parity(snapshots: dict[str, dict]) -> None:
    """The full transition chain produces identical live + settled outcomes."""
    json_snap = snapshots["json"]
    refs_snap = snapshots["git-refs"]

    # Blocker reached the terminal merged state in both backends.
    assert json_snap["settled"]["blocker"]["state"] == "merged"
    assert refs_snap["settled"]["blocker"]["state"] == "merged"
    # And the whole normalized snapshot is equivalent across backends.
    assert json_snap == refs_snap


def test_set_stage_parity(snapshots: dict[str, dict]) -> None:
    """set-stage records the same stage + history entry on both backends."""
    for backend in ("json", "git-refs"):
        blocker = snapshots[backend]["settled"]["blocker"]
        assert blocker["stage"] == "implemented"
        stage_entries = [
            h for h in blocker["history"] if h.get("evidence", {}).get("kind") == "stage"
        ]
        assert len(stage_entries) == 1
        assert stage_entries[0]["to"] == "implemented"
        assert stage_entries[0]["by"] == "orch"

    assert snapshots["json"] == snapshots["git-refs"]


def test_dependent_promotion_parity(snapshots: dict[str, dict]) -> None:
    """Sealing the blocker promotes its dependent identically on both backends."""
    for backend in ("json", "git-refs"):
        live = snapshots[backend]["live"]
        assert "blocker" not in live  # sealed out of the live queue
        dependent = live["dependent"]
        assert dependent["state"] == "ready"
        assert dependent["pending_blockers"] == 0
        release = [h for h in dependent["history"] if h.get("by") == "release"]
        assert len(release) == 1
        assert release[0]["from"] == "blocked"
        assert release[0]["to"] == "ready"

    assert snapshots["json"] == snapshots["git-refs"]


def test_sealing_parity_settled_history_identical(snapshots: dict[str, dict]) -> None:
    """The settled JSONL record is byte-for-byte equivalent (timestamps aside)."""
    json_blocker = snapshots["json"]["settled"]["blocker"]
    refs_blocker = snapshots["git-refs"]["settled"]["blocker"]

    assert json_blocker == refs_blocker

    # The sealed history records the full recorded-forward chain plus the
    # set-stage entry, in the same order on both backends.
    chain = [(h["from"], h["to"]) for h in json_blocker["history"]]
    assert chain == [
        ("planned", "ready"),
        ("ready", "in_progress"),
        (None, "implemented"),  # set-stage entry (from=None when no prior stage)
        ("in_progress", "awaiting_merge"),
        ("awaiting_merge", "merged"),
    ]

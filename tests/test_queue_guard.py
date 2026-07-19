"""Tests for the queue mutation guard (run lease + tamper-evident writes)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "aet-work" / "lib"))

from aet_queue import (  # noqa: E402
    QueueIntegrityError,
    acquire_lease,
    check_lease,
    lease_path,
    read_queue,
    release_lease,
    write_queue,
)


def _load_bin(name: str):
    """Load an extension-less aet-work bin script as a module."""
    path = REPO_ROOT / "aet-work" / "bin" / name
    loader = SourceFileLoader(f"aet_bin_{name}", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _write_plan(plans_dir: Path, stem: str) -> Path:
    """Write a plan file that passes the full intake validation suite."""
    plans_dir.mkdir(parents=True, exist_ok=True)

    # Create a default PRD in the canonical layout for rtrace resolution.
    if plans_dir.name == "plans" and plans_dir.parent.name == "docs":
        repo_root = plans_dir.parent.parent
    else:
        repo_root = plans_dir.parent
    prds_dir = repo_root / "docs" / "prds"
    prds_dir.mkdir(parents=True, exist_ok=True)
    prd_path = prds_dir / "default-prd.md"
    if not prd_path.exists():
        prd_path.write_text(
            "# Default PRD\n\n## Requirements\n- **R-1**: default requirement\n",
            encoding="utf-8",
        )

    plan = plans_dir / f"{stem}.md"
    plan.write_text(
        f"---\n"
        f"id: {stem}\n"
        f"size: S\n"
        f"---\n\n"
        f"# {stem}\n\n"
        f"## Context\n"
        f"PRD: docs/prds/default-prd.md\n\n"
        f"## Task List\n"
        f"1. Do something (traces: R-1).\n\n"
        f"## Files to Modify\n"
        f"- `src/widget.py` (new)\n\n"
        f"## Validation Steps\n"
        f"- [ ] test_widget_creation verifies widget.py\n\n"
        f"_Stage: plan-approved_\n",
        encoding="utf-8",
    )
    return plan


def _dead_pid() -> int:
    """Return a PID that is guaranteed not to be alive anymore."""
    proc = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])
    proc.wait()
    return proc.pid


def _clear_run_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AET_RUN_ID", raising=False)


# ---------------------------------------------------------------------------
# Run lease
# ---------------------------------------------------------------------------


def test_add_refused_while_lease_held_by_live_run(tmp_path, monkeypatch, capsys):
    """A foreign live lease makes `aet sprint add` refuse before writing."""
    _clear_run_env(monkeypatch)
    qf = tmp_path / ".agents" / "work-queue.json"
    hf = tmp_path / ".agents" / "work-history.jsonl"
    qf.parent.mkdir(parents=True, exist_ok=True)
    hf.touch()
    plan = _write_plan(tmp_path / "docs" / "plans", "feat-add")

    # A live lease owned by a different run (our PID is alive, run_id is foreign).
    acquire_lease(str(qf), "foreign-run")

    sprint = _load_bin("sprint")
    rc = sprint.main([
        "add",
        str(plan),
        "--queue-file", str(qf),
        "--history-file", str(hf),
        "--plans-dir", str(plan.parent),
        "--config", str(tmp_path / "missing-config.json"),
    ])

    assert rc == 1
    captured = capsys.readouterr()
    assert "foreign-run" in captured.err
    assert not qf.exists()  # refused before writing the queue


def test_child_with_matching_run_id_allowed(tmp_path, monkeypatch):
    """A caller whose AET_RUN_ID matches the live lease may mutate."""
    qf = tmp_path / ".agents" / "work-queue.json"
    qf.parent.mkdir(parents=True, exist_ok=True)

    acquire_lease(str(qf), "run-X")
    monkeypatch.setenv("AET_RUN_ID", "run-X")

    # Should not raise.
    check_lease(str(qf))


def test_stale_lease_dead_pid_reclaimed_with_warning(tmp_path, monkeypatch, capsys):
    """A lease whose PID is dead is reclaimed with a warning."""
    _clear_run_env(monkeypatch)
    qf = tmp_path / ".agents" / "work-queue.json"
    qf.parent.mkdir(parents=True, exist_ok=True)
    lp = lease_path(str(qf))
    Path(lp).write_text(
        json.dumps({"run_id": "dead-run", "pid": _dead_pid(), "started_at": "x"}),
        encoding="utf-8",
    )

    check_lease(str(qf))

    captured = capsys.readouterr()
    assert "stale" in captured.err.lower()
    assert not Path(lp).exists()  # reclaimed


def test_force_overrides_lease_with_warning(tmp_path, monkeypatch, capsys):
    """--force lets a mutation proceed despite a foreign live lease."""
    _clear_run_env(monkeypatch)
    qf = tmp_path / ".agents" / "work-queue.json"
    hf = tmp_path / ".agents" / "work-history.jsonl"
    qf.parent.mkdir(parents=True, exist_ok=True)
    hf.touch()
    plan = _write_plan(tmp_path / "docs" / "plans", "feat-force")

    acquire_lease(str(qf), "foreign-run")

    sprint = _load_bin("sprint")
    rc = sprint.main([
        "add",
        str(plan),
        "--queue-file", str(qf),
        "--history-file", str(hf),
        "--plans-dir", str(plan.parent),
        "--config", str(tmp_path / "missing-config.json"),
        "--force",
    ])

    assert rc == 0
    captured = capsys.readouterr()
    assert "foreign-run" in captured.err
    assert qf.exists()  # write proceeded


def test_lease_released_on_batch_crash(tmp_path):
    """The finally path releases a held lease even when the run crashes."""
    qf = tmp_path / ".agents" / "work-queue.json"
    qf.parent.mkdir(parents=True, exist_ok=True)
    lp = lease_path(str(qf))

    acquire_lease(str(qf), "run-crash")
    assert Path(lp).exists()

    with pytest.raises(RuntimeError):
        try:
            raise RuntimeError("simulated batch crash")
        finally:
            release_lease(str(qf), "run-crash")

    assert not Path(lp).exists()


# ---------------------------------------------------------------------------
# Tamper-evident writes
# ---------------------------------------------------------------------------


def test_read_fails_closed_on_content_hash_mismatch(tmp_path):
    """Hand-editing a stamped queue makes read_queue raise QueueIntegrityError."""
    qf = tmp_path / "work-queue.json"
    write_queue(str(qf), [{"id": "t1", "state": "ready"}], wrapper={"source_prd": "x"})

    data = json.loads(qf.read_text(encoding="utf-8"))
    data["tasks"][0]["state"] = "in_progress"  # tamper
    qf.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(QueueIntegrityError):
        read_queue(str(qf))


def test_revision_increments_monotonically(tmp_path):
    """Each wrapper write bumps revision by exactly one."""
    qf = tmp_path / "work-queue.json"
    write_queue(str(qf), [{"id": "t1", "state": "ready"}], wrapper={"source_prd": "x"})
    assert json.loads(qf.read_text(encoding="utf-8"))["revision"] == 1

    queue = read_queue(str(qf))
    write_queue(str(qf), queue, wrapper={"source_prd": "x"})
    assert json.loads(qf.read_text(encoding="utf-8"))["revision"] == 2


def test_legacy_queue_without_stamp_accepted_then_stamped(tmp_path):
    """A legacy wrapper without revision/hash is read, then stamped on write."""
    qf = tmp_path / "work-queue.json"
    legacy = {"source_prd": "x", "tasks": [{"id": "t1", "state": "ready"}]}
    qf.write_text(json.dumps(legacy), encoding="utf-8")

    queue = read_queue(str(qf))  # accepted: no stamp to verify
    assert queue[0]["id"] == "t1"

    write_queue(str(qf), queue)
    data = json.loads(qf.read_text(encoding="utf-8"))
    assert data["revision"] == 1
    assert "content_hash" in data


# ---------------------------------------------------------------------------
# Integrity recovery: audit / heal must work on a tampered queue
# ---------------------------------------------------------------------------


class _MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _no_git(cmd, **kwargs):
    """subprocess.run stand-in: every git/gh call fails (no repo, no branches)."""
    return _MockResult(1, "", "")


def _stamp_and_tamper(qf: Path, task: dict) -> int:
    """Write a stamped queue, hand-edit the tasks, return the stamped revision.

    Mirrors the reported failure: an external edit changes the tasks array
    without restamping the envelope's content_hash.
    """
    write_queue(str(qf), [task], wrapper={"source_prd": "x"})
    data = json.loads(qf.read_text(encoding="utf-8"))
    revision = data["revision"]
    data["tasks"][0]["worktree"] = None  # external edit; hash left stale
    qf.write_text(json.dumps(data), encoding="utf-8")
    return revision


def _write_plan_file(tmp_path: Path, task_id: str) -> str:
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir(exist_ok=True)
    plan = plans_dir / f"{task_id}.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    return str(plan)


def test_audit_runs_on_tampered_queue_and_warns(tmp_path, capsys):
    """The remedy named in the error message must survive the mismatch itself."""
    aet_state = _load_bin("aet-state")
    qf = tmp_path / "work-queue.json"
    plan = _write_plan_file(tmp_path, "t1")
    _stamp_and_tamper(qf, {"id": "t1", "state": "ready", "plan_file": plan})

    args = aet_state.argparse.Namespace(command="audit", queue=str(qf))
    with patch.object(aet_state.subprocess, "run", side_effect=_no_git):
        rc = aet_state.cmd_audit(args)

    assert rc == 0
    captured = capsys.readouterr()
    assert "integrity check failed" in captured.err
    results = json.loads(captured.out)
    assert results["t1"]["stored"] == "ready"


def test_heal_dry_run_tolerates_tamper_without_restamping(tmp_path, capsys):
    """Dry-run heal reports the stale envelope but must not mutate the queue."""
    aet_state = _load_bin("aet-state")
    qf = tmp_path / "work-queue.json"
    plan = _write_plan_file(tmp_path, "t1")
    _stamp_and_tamper(qf, {"id": "t1", "state": "ready", "plan_file": plan})

    args = aet_state.argparse.Namespace(
        command="heal", queue=str(qf), apply=False, force=False
    )
    with patch.object(aet_state.subprocess, "run", side_effect=_no_git):
        rc = aet_state.cmd_heal(args)

    assert rc == 0
    captured = capsys.readouterr()
    assert "No healable discrepancies found." in captured.out
    assert "run with --apply to restamp" in captured.out
    # Dry run left the stale envelope untouched.
    with pytest.raises(QueueIntegrityError):
        read_queue(str(qf))


def test_heal_apply_restamps_envelope_with_no_state_changes(tmp_path, capsys):
    """The reported scenario: states match git, only the envelope is stale."""
    aet_state = _load_bin("aet-state")
    qf = tmp_path / "work-queue.json"
    plan = _write_plan_file(tmp_path, "t1")
    revision = _stamp_and_tamper(
        qf, {"id": "t1", "state": "ready", "plan_file": plan}
    )

    args = aet_state.argparse.Namespace(
        command="heal", queue=str(qf), apply=True, force=False
    )
    with patch.object(aet_state.subprocess, "run", side_effect=_no_git):
        rc = aet_state.cmd_heal(args)

    assert rc == 0
    captured = capsys.readouterr()
    assert "Restamped queue integrity envelope" in captured.out
    # Verified reads pass again, the revision advanced, and the external
    # edit itself is preserved (heal restamps, it does not revert).
    queue = read_queue(str(qf))
    assert queue[0]["worktree"] is None
    data = json.loads(qf.read_text(encoding="utf-8"))
    assert data["revision"] == revision + 1


def test_heal_apply_restamps_and_applies_state_fix(tmp_path, capsys):
    """A tampered queue with a real discrepancy heals and verifies afterwards."""
    aet_state = _load_bin("aet-state")
    qf = tmp_path / "work-queue.json"
    plan = _write_plan_file(tmp_path, "t1")
    _stamp_and_tamper(qf, {"id": "t1", "state": "planned", "plan_file": plan})

    args = aet_state.argparse.Namespace(
        command="heal", queue=str(qf), apply=True, force=False
    )
    with patch.object(aet_state.subprocess, "run", side_effect=_no_git):
        rc = aet_state.cmd_heal(args)

    assert rc == 0
    captured = capsys.readouterr()
    assert "Healed 1 task(s); 0 failed." in captured.out
    queue = read_queue(str(qf))  # verified read must not raise
    assert queue[0]["state"] == "ready"


# ---------------------------------------------------------------------------
# Integrity refusal: mutating bins fail closed with a clean one-liner, never
# a traceback, and every refusal names the audit/heal recovery path.
# ---------------------------------------------------------------------------


def _tampered_queue(tmp_path: Path) -> Path:
    """Write a stamped queue and hand-edit it so the envelope is stale."""
    qf = tmp_path / "work-queue.json"
    plan = _write_plan_file(tmp_path, "t1")
    _stamp_and_tamper(qf, {"id": "t1", "state": "ready", "plan_file": plan})
    return qf


def _assert_clean_refusal(rc: int, err: str) -> None:
    assert rc == 1
    assert "queue modified outside aet state" in err
    assert "aet state audit" in err
    assert "aet state heal --apply" in err
    assert "Traceback" not in err


def test_next_refuses_cleanly_on_tampered_queue(tmp_path, monkeypatch, capsys):
    nxt = _load_bin("next")
    qf = _tampered_queue(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["next", "--queue-file", str(qf)])

    rc = nxt.main()

    _assert_clean_refusal(rc, capsys.readouterr().err)


def test_sync_refuses_cleanly_on_tampered_queue(tmp_path, monkeypatch, capsys):
    sync = _load_bin("sync")
    qf = _tampered_queue(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["sync", "--queue-file", str(qf)])

    rc = sync.main()

    _assert_clean_refusal(rc, capsys.readouterr().err)


def test_add_refuses_cleanly_on_tampered_queue(tmp_path, monkeypatch, capsys):
    sprint = _load_bin("sprint")
    qf = _tampered_queue(tmp_path)
    plans_dir = tmp_path / "plans"
    plan = _write_plan(plans_dir, "t2")
    monkeypatch.chdir(tmp_path)

    rc = sprint.main(["add", plan.stem, "--queue-file", str(qf), "--plans-dir", str(plans_dir)])

    _assert_clean_refusal(rc, capsys.readouterr().err)


def test_init_queue_refuses_cleanly_on_tampered_queue(tmp_path, monkeypatch, capsys):
    init_queue = _load_bin("init-queue")
    qf = _tampered_queue(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["init-queue", "--queue-file", str(qf)])

    rc = init_queue.main()

    _assert_clean_refusal(rc, capsys.readouterr().err)

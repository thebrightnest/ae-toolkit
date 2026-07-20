"""Tests for aet-work desk — risk-ranked awaiting_merge view + evidence bundle."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parents[2]
_DESK_PY = REPO_ROOT / "src" / "aet" / "cli" / "desk.py"

_desk_spec = importlib.util.spec_from_loader(
    "desk_bin", importlib.machinery.SourceFileLoader("desk_bin", str(_DESK_PY))
)
desk = importlib.util.module_from_spec(_desk_spec)
_desk_spec.loader.exec_module(desk)

from aet import (  # noqa: E402
    project_id,
    telemetry,
)


def _plan_path(tmp_path: Path, plan_id: str) -> Path:
    return tmp_path / "plans" / f"{plan_id}.md"


def _write_plan(
    tmp_path: Path,
    plan_id: str,
    size: str = "M",
    work_class: str | None = None,
    security_review: str | None = None,
    docs_sync: str | None = None,
) -> Path:
    plan_dir = tmp_path / "plans"
    plan_dir.mkdir(exist_ok=True)
    lines = ["---", f"id: {plan_id}", f"size: {size}"]
    if work_class:
        lines.append(f"work_class: {work_class}")
    if security_review:
        lines.append(f"security_review: {security_review}")
        if security_review == "skipped":
            lines.append("security_review_reason: test reason")
    if docs_sync:
        lines.append(f"docs_sync: {docs_sync}")
        if docs_sync == "skipped":
            lines.append("docs_sync_reason: test reason")
    lines.extend(["---", "", f"# {plan_id}", ""])
    path = _plan_path(tmp_path, plan_id)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_queue(tmp_path: Path, tasks: list[dict]) -> str:
    path = tmp_path / "queue.json"
    path.write_text(json.dumps(tasks), encoding="utf-8")
    return str(path)


def _write_history(tmp_path: Path) -> str:
    path = tmp_path / "history.jsonl"
    path.write_text("", encoding="utf-8")
    return str(path)


def _evidence_dir(tmp_path: Path) -> Path:
    # Match the runtime slug derivation used by ``evidence.evidence_path``.
    return tmp_path / "reports" / project_id.derive_project_slug()


def _write_evidence(
    tmp_path: Path,
    task_id: str,
    kind: str,
    verdict: str,
    summary: str = "",
    **extra: object,
) -> None:
    record: dict[str, object] = {
        "task_id": task_id,
        "stage": kind,
        "skill": f"aet-{kind}",
        "verdict": verdict,
        "summary": summary,
        "generated_at": "2026-07-16T00:00:00Z",
        "tree_hash": "abc",
    }
    if kind == "qa":
        record.setdefault("test_command", "pytest")
        record.setdefault("tests_total", extra.get("tests_total", 10))
        record.setdefault("tests_passed", extra.get("tests_passed", 9))
        record.setdefault("tests_failed", extra.get("tests_failed", 1))
    else:
        record.setdefault("findings", extra.get("findings", []))
        if kind == "sync-docs":
            record["divergences"] = record.pop("findings")
    path = _evidence_dir(tmp_path) / task_id / f"{kind}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")


def _append_telemetry(tmp_path: Path, task_id: str, *records: dict) -> None:
    # Match the runtime repo-root/slug derivation used by the desk command.
    logger = telemetry.RunLogger(repo_root=str(project_id.resolve_repo_root()))
    for record in records:
        logger.append_record(record, task_id)


def _run_desk(queue_file: str, history_file: str, plans_dir: str, json_mode: bool = False) -> str:
    argv = [
        "desk",
        "--queue-file", queue_file,
        "--history-file", history_file,
        "--plans-dir", plans_dir,
    ]
    if json_mode:
        argv.append("--json")
    stdout = io.StringIO()
    with patch.object(sys, "argv", argv), redirect_stdout(stdout):
        rc = desk.main()
    assert rc == 0
    return stdout.getvalue()


def _desk_json(queue_file: str, history_file: str, plans_dir: str) -> dict:
    output = _run_desk(queue_file, history_file, plans_dir, json_mode=True)
    return json.loads(output)


@pytest.fixture(autouse=True)
def _isolate_reports_dir(monkeypatch, tmp_path):
    """Point the evidence and telemetry archives at per-test tmp dirs.

    Isolating ``AET_TELEMETRY_ARCHIVE_DIR`` keeps the telemetry-signal path
    hermetic — otherwise the desk reads the real ``~/.aet`` archive and a live
    run logged under a colliding task id could perturb the risk score.
    """
    monkeypatch.setenv("AET_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("AET_TELEMETRY_ARCHIVE_DIR", str(tmp_path / "telemetry"))


class TestDeskListsOnlyAwaitingMerge:
    def test_lists_only_awaiting_merge(self, tmp_path):
        for tid, state in [
            ("t1", "awaiting_merge"),
            ("t2", "ready"),
            ("t3", "in_progress"),
            ("t4", "merged"),
        ]:
            _write_plan(tmp_path, tid)
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(_plan_path(tmp_path, "t1")),
                },
                {
                    "id": "t2",
                    "state": "ready",
                    "title": "Two",
                    "plan_file": str(_plan_path(tmp_path, "t2")),
                },
                {
                    "id": "t3",
                    "state": "in_progress",
                    "title": "Three",
                    "plan_file": str(_plan_path(tmp_path, "t3")),
                },
                {
                    "id": "t4",
                    "state": "merged",
                    "title": "Four",
                    "plan_file": str(_plan_path(tmp_path, "t4")),
                },
            ],
        )
        history_file = _write_history(tmp_path)
        payload = _desk_json(queue_file, history_file, str(tmp_path / "plans"))
        assert payload["summary"]["awaiting_merge"] == 1
        assert [t["id"] for t in payload["tasks"]] == ["t1"]


class TestDeskEvidenceBundle:
    def test_evidence_bundle_attached_per_task(self, tmp_path):
        _write_plan(tmp_path, "t1")
        _write_evidence(tmp_path, "t1", "qa", "pass", "qa ok", tests_total=8, tests_passed=8, tests_failed=0)
        _write_evidence(tmp_path, "t1", "review", "fail", "review issues", findings=["a", "b"])
        _write_evidence(tmp_path, "t1", "cso", "pass", "cso ok", findings=[])
        _write_evidence(tmp_path, "t1", "sync-docs", "pass", "docs ok", divergences=[])
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(_plan_path(tmp_path, "t1")),
                }
            ],
        )
        history_file = _write_history(tmp_path)
        payload = _desk_json(queue_file, history_file, str(tmp_path / "plans"))
        task = payload["tasks"][0]
        ev = task["evidence"]
        assert ev["qa"]["present"] is True
        assert ev["qa"]["tests_total"] == 8
        assert ev["review"]["findings_count"] == 2
        assert ev["cso"]["verdict"] == "pass"
        assert ev["sync-docs"]["verdict"] == "pass"

    def test_missing_required_verdict_shown_as_gap(self, tmp_path):
        _write_plan(tmp_path, "t1", security_review="skipped", docs_sync="required")
        _write_evidence(tmp_path, "t1", "qa", "pass")
        _write_evidence(tmp_path, "t1", "review", "pass")
        # cso skipped by plan, sync-docs missing
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(_plan_path(tmp_path, "t1")),
                }
            ],
        )
        history_file = _write_history(tmp_path)
        payload = _desk_json(queue_file, history_file, str(tmp_path / "plans"))
        task = payload["tasks"][0]
        assert task["evidence"]["cso"]["required"] is False
        assert task["evidence"]["sync-docs"]["present"] is False
        assert task["evidence"]["sync-docs"]["required"] is True
        assert "sync-docs" in task["gaps"]

        human = _run_desk(queue_file, history_file, str(tmp_path / "plans"))
        assert "sync-docs: missing (required)" in human


class TestDeskRiskOrdering:
    def test_risk_order_stable_across_runs(self, tmp_path):
        for tid in ("risky", "safe"):
            _write_plan(tmp_path, tid)
        _write_evidence(tmp_path, "risky", "review", "fail", findings=["x"])
        _write_evidence(tmp_path, "safe", "review", "pass", findings=[])
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "risky",
                    "state": "awaiting_merge",
                    "title": "Risky",
                    "plan_file": str(_plan_path(tmp_path, "risky")),
                },
                {
                    "id": "safe",
                    "state": "awaiting_merge",
                    "title": "Safe",
                    "plan_file": str(_plan_path(tmp_path, "safe")),
                },
            ],
        )
        history_file = _write_history(tmp_path)
        order1 = [t["id"] for t in _desk_json(queue_file, history_file, str(tmp_path / "plans"))["tasks"]]
        order2 = [t["id"] for t in _desk_json(queue_file, history_file, str(tmp_path / "plans"))["tasks"]]
        assert order1 == order2 == ["risky", "safe"]

    def test_critical_outranks_trivial(self, tmp_path):
        for tid, wc in [("crit", "critical"), ("triv", "trivial")]:
            _write_plan(tmp_path, tid, work_class=wc)
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "triv",
                    "state": "awaiting_merge",
                    "title": "Trivial",
                    "plan_file": str(_plan_path(tmp_path, "triv")),
                    "work_class": "trivial",
                },
                {
                    "id": "crit",
                    "state": "awaiting_merge",
                    "title": "Critical",
                    "plan_file": str(_plan_path(tmp_path, "crit")),
                    "work_class": "critical",
                },
            ],
        )
        history_file = _write_history(tmp_path)
        payload = _desk_json(queue_file, history_file, str(tmp_path / "plans"))
        assert [t["id"] for t in payload["tasks"]] == ["crit", "triv"]

    def test_unclassified_ranks_elevated(self, tmp_path):
        for tid, wc in [("uncls", None), ("triv", "trivial")]:
            _write_plan(tmp_path, tid, work_class=wc)
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "triv",
                    "state": "awaiting_merge",
                    "title": "Trivial",
                    "plan_file": str(_plan_path(tmp_path, "triv")),
                    "work_class": "trivial",
                },
                {
                    "id": "uncls",
                    "state": "awaiting_merge",
                    "title": "Unclassified",
                    "plan_file": str(_plan_path(tmp_path, "uncls")),
                },
            ],
        )
        history_file = _write_history(tmp_path)
        payload = _desk_json(queue_file, history_file, str(tmp_path / "plans"))
        scores = {t["id"]: t["risk_score"] for t in payload["tasks"]}
        assert scores["uncls"] > scores["triv"]
        assert [t["id"] for t in payload["tasks"]] == ["uncls", "triv"]


class TestDeskJsonProjection:
    def test_json_projection_matches_human_view(self, tmp_path):
        _write_plan(tmp_path, "t1", size="M", work_class="critical")
        _write_evidence(tmp_path, "t1", "review", "fail", findings=["a"])
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(_plan_path(tmp_path, "t1")),
                    "work_class": "critical",
                }
            ],
        )
        history_file = _write_history(tmp_path)
        payload = _desk_json(queue_file, history_file, str(tmp_path / "plans"))
        human = _run_desk(queue_file, history_file, str(tmp_path / "plans"))
        task = payload["tasks"][0]
        assert str(task["risk_score"]) in human
        assert "work_class=critical" in human
        assert task["evidence"]["review"]["findings_count"] == 1


class TestDeskDispatcher:
    def test_desk_routed_through_aet_dispatcher(self, tmp_path):
        _write_plan(tmp_path, "t1")
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(_plan_path(tmp_path, "t1")),
                }
            ],
        )
        history_file = _write_history(tmp_path)
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "src" / "aet" / "cli" / "main.py"),
                "desk",
                "--json",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(tmp_path / "plans"),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["summary"]["awaiting_merge"] == 1
        assert payload["tasks"][0]["id"] == "t1"


class TestDeskTelemetrySignals:
    def test_files_modified_and_tests_failed_raise_risk(self, tmp_path):
        _write_plan(tmp_path, "t1")
        # Two stage records for t1: the later end_time wins (3 files, not 5).
        # Two test_run records: the highest tests_failed drives the signal.
        _append_telemetry(
            tmp_path,
            "t1",
            {
                "type": "stage",
                "task_id": "t1",
                "end_time": "2026-07-16T00:01:00Z",
                "files_modified": ["a.py", "b.py", "c.py", "d.py", "e.py"],
            },
            {
                "type": "stage",
                "task_id": "t1",
                "end_time": "2026-07-16T00:05:00Z",
                "files_modified": ["a.py", "b.py", "c.py"],
            },
            {"type": "test_run", "task_id": "t1", "tests_failed": 2},
            {"type": "test_run", "task_id": "t1", "tests_failed": 4},
        )
        # A different task's telemetry must not leak into t1's signals.
        _append_telemetry(
            tmp_path,
            "other",
            {
                "type": "stage",
                "task_id": "other",
                "end_time": "2026-07-16T09:00:00Z",
                "files_modified": ["z.py"],
            },
        )
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(_plan_path(tmp_path, "t1")),
                }
            ],
        )
        history_file = _write_history(tmp_path)
        payload = _desk_json(queue_file, history_file, str(tmp_path / "plans"))
        factors = payload["tasks"][0]["factors"]
        assert "files_modified=3" in factors
        assert "tests_failed>0" in factors

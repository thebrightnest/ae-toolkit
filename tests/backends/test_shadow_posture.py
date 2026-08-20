"""Tests for shadow posture: local by default, announced, never pushed."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from aet.backends.base import SHADOW_POSTURE, SHARED_POSTURE
from aet.backends.factory import (
    create_backend,
    resolve_posture,
)
from aet.backends.git_refs_backend import GitRefsBackend
from aet.projections.dispatcher import resolve_projections


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test User"],
        check=True,
    )
    (path / ".agents").mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "initial"], check=True)
    return path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return _init_repo(tmp_path / "project")


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


class TestPostureInference:
    """Posture is inferred from the presence or absence of project-scope config."""

    def test_no_config_is_shadow(self, project: Path, home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: home)
        posture = resolve_posture(
            str(project / ".agents" / "aet-config.json"),
            repo_root=str(project),
        )
        assert posture == SHADOW_POSTURE

    def test_in_tree_config_is_shared(self, project: Path, home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: home)
        config_path = project / ".agents" / "aet-config.json"
        config_path.write_text(json.dumps({"integration_mode": "single-pr"}), encoding="utf-8")
        posture = resolve_posture(str(config_path), repo_root=str(project))
        assert posture == SHARED_POSTURE

    def test_user_config_without_project_config_is_shadow(
        self, project: Path, home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: home)
        slug = "test-project"
        external = home / ".aet" / slug / "config.json"
        external.parent.mkdir(parents=True, exist_ok=True)
        external.write_text(json.dumps({"integration_mode": "single-pr"}), encoding="utf-8")

        with patch.dict(os.environ, {"AET_PROJECT_ID": slug}, clear=True):
            posture = resolve_posture(
                str(project / ".agents" / "aet-config.json"),
                repo_root=str(project),
            )
        assert posture == SHADOW_POSTURE

    def test_create_backend_attaches_posture(self, project: Path, home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: home)
        backend = create_backend(
            config_path=str(project / ".agents" / "aet-config.json"),
            queue_file=str(project / ".agents" / "aet-queue"),
            history_file=str(project / ".agents" / "work-history.jsonl"),
        )
        assert backend.posture == SHADOW_POSTURE


class TestShadowPush:
    """In shadow posture refs/aet/* is never pushed."""

    def test_best_effort_push_is_no_op_in_shadow(self, project: Path) -> None:
        backend = GitRefsBackend(
            queue_file=str(project / ".agents" / "aet-queue"),
            history_file=str(project / ".agents" / "work-history.jsonl"),
            posture=SHADOW_POSTURE,
        )
        # Even with a remote configured, shadow posture suppresses the push.
        with patch("aet.backends.git_refs_backend._has_remote", return_value=True):
            with patch("aet.backends.git_refs_backend.subprocess.run") as mock_run:
                result = backend.push()
        assert result is True
        mock_run.assert_not_called()

    def test_mandatory_push_raises_adr_055_exemption(self, project: Path) -> None:
        backend = GitRefsBackend(
            queue_file=str(project / ".agents" / "aet-queue"),
            history_file=str(project / ".agents" / "work-history.jsonl"),
            posture=SHADOW_POSTURE,
        )
        with pytest.raises(GitRefsBackend.RefsPushError) as ctx:
            backend.push(mandatory=True)
        msg = str(ctx.value)
        assert "ADR-055" in msg
        assert "exempt" in msg.lower()
        assert "shadow" in msg.lower()

    def test_shared_posture_pushes_normally(self, project: Path) -> None:
        backend = GitRefsBackend(
            queue_file=str(project / ".agents" / "aet-queue"),
            history_file=str(project / ".agents" / "work-history.jsonl"),
            posture=SHARED_POSTURE,
        )
        with patch("aet.backends.git_refs_backend._has_remote", return_value=True):
            with patch("aet.backends.git_refs_backend.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = b""
                mock_run.return_value.stderr = b""
                result = backend.push()
        assert result is True
        mock_run.assert_called()


class TestShadowSeal:
    """In shadow posture seal drops the task ref but leaves the working tree clean."""

    def test_shadow_seal_skips_history_file(self, project: Path) -> None:
        backend = GitRefsBackend(
            queue_file=str(project / ".agents" / "aet-queue"),
            history_file=str(project / ".agents" / "work-history.jsonl"),
            posture=SHADOW_POSTURE,
        )
        task = {"id": "t-1", "state": "in_progress", "title": "task 1"}
        backend.save([task])
        backend.seal("t-1", str(project / ".agents" / "work-history.jsonl"))

        history_file = project / ".agents" / "work-history.jsonl"
        assert not history_file.exists()

    def test_shared_seal_writes_history_file(self, project: Path) -> None:
        backend = GitRefsBackend(
            queue_file=str(project / ".agents" / "aet-queue"),
            history_file=str(project / ".agents" / "work-history.jsonl"),
            posture=SHARED_POSTURE,
        )
        task = {"id": "t-1", "state": "in_progress", "title": "task 1"}
        backend.save([task])
        backend.seal("t-1", str(project / ".agents" / "work-history.jsonl"))

        history_file = project / ".agents" / "work-history.jsonl"
        assert history_file.exists()


class TestShadowProjections:
    """In shadow posture no projections run."""

    def test_resolve_projections_returns_empty_dispatcher_in_shadow(self) -> None:
        dispatcher = resolve_projections(
            {"projections": [{"type": "github", "repo": "foo/bar"}]},
            posture=SHADOW_POSTURE,
        )
        assert dispatcher.projections == []

    def test_resolve_projections_returns_configured_projections_when_shared(self) -> None:
        dispatcher = resolve_projections(
            {"projections": [{"type": "github", "repo": "foo/bar"}]},
            posture=SHARED_POSTURE,
        )
        assert len(dispatcher.projections) == 1


class TestShadowAnnouncement:
    """Shadow posture is announced on every orchestrator run."""

    def test_announce_posture_prints_shadow_notice(self, capsys: pytest.CaptureFixture) -> None:
        from aet.cli.orchestrator import _announce_posture

        _announce_posture(SHADOW_POSTURE)
        captured = capsys.readouterr()
        assert "Shadow posture" in captured.out
        assert "refs/aet/* will not be pushed" in captured.out
        assert "aet configure --scope team" in captured.out

    def test_announce_posture_is_silent_for_shared(self, capsys: pytest.CaptureFixture) -> None:
        from aet.cli.orchestrator import _announce_posture

        _announce_posture(SHARED_POSTURE)
        captured = capsys.readouterr()
        assert captured.out == ""

"""Unit tests for validation.pre_integration_check (ADR-078 / R-2)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from aet.evidence import LINT_ONLY, RUN, SKIP, FreshnessResult
from aet.validation import CheckResult, pre_integration_check


def _subproc_mock(stdout="", stderr="", returncode=0, side_effect=None):
    _real_run = subprocess.run

    def _run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd and cmd[0] == "git":
            return _real_run(cmd, *args, **kwargs)
        if side_effect:
            raise side_effect
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    return _run


def test_check_result_fields():
    res = CheckResult(decision=SKIP, ran=None, ok=True, output="")
    assert res.decision == SKIP
    assert res.ran is None
    assert res.ok is True
    assert res.output == ""


def test_skip_runs_no_subprocess(tmp_path: Path):
    with patch(
        "aet.validation.evidence.validation_freshness",
        return_value=FreshnessResult(SKIP, "tree unchanged", "h1", "h1"),
    ), patch("aet.validation.subprocess.run", side_effect=_subproc_mock()) as mock_subproc:
        res = pre_integration_check("task-1", worktree_dir=tmp_path)
        assert res.decision == SKIP
        assert res.ran is None
        assert res.ok is True
        assert res.output == ""
        # Only git calls, no validation command calls
        non_git_calls = [c for c in mock_subproc.call_args_list if c.args[0][0] != "git"]
        assert non_git_calls == []


def test_lint_only_uses_lint_command_when_configured(tmp_path: Path):
    cfg_dir = tmp_path / ".agents"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "aet-config.json").write_text(
        '{"validate_command": "make validate", "lint_command": "ruff check"}',
        encoding="utf-8",
    )
    mock = _subproc_mock(stdout="lint ok\n")
    with patch(
        "aet.validation.evidence.validation_freshness",
        return_value=FreshnessResult(LINT_ONLY, "only non-code changed", "h1", "h2", ["a.md"]),
    ), patch("aet.validation.subprocess.run", side_effect=mock) as mock_subproc:
        res = pre_integration_check("task-1", worktree_dir=tmp_path)
        assert res.decision == LINT_ONLY
        assert res.ran == ["ruff", "check"]
        assert res.ok is True
        assert res.output == "lint ok\n"
        non_git_calls = [c for c in mock_subproc.call_args_list if c.args[0][0] != "git"]
        assert len(non_git_calls) == 1
        assert non_git_calls[0].args[0] == ["ruff", "check"]
        assert non_git_calls[0].kwargs.get("cwd") == str(tmp_path)


def test_lint_only_falls_back_to_validate_command_when_lint_unset(tmp_path: Path):
    cfg_dir = tmp_path / ".agents"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "aet-config.json").write_text(
        '{"validate_command": "make test"}',
        encoding="utf-8",
    )
    mock = _subproc_mock(stdout="make test ok\n")
    with patch(
        "aet.validation.evidence.validation_freshness",
        return_value=FreshnessResult(LINT_ONLY, "only non-code changed", "h1", "h2", ["a.md"]),
    ), patch("aet.validation.subprocess.run", side_effect=mock):
        res = pre_integration_check("task-1", worktree_dir=tmp_path)
        assert res.decision == LINT_ONLY
        assert res.ran == ["make", "test"]
        assert res.ok is True
        assert res.output == "make test ok\n"


def test_run_uses_validate_command_on_missing_or_failed_verdict(tmp_path: Path):
    mock = _subproc_mock(stdout="validated\n")
    with patch(
        "aet.validation.evidence.validation_freshness",
        return_value=FreshnessResult(RUN, "no prior verdict", "", "h2"),
    ), patch("aet.validation.subprocess.run", side_effect=mock):
        res = pre_integration_check("task-1", worktree_dir=tmp_path)
        assert res.decision == RUN
        assert res.ran == ["make", "validate"]
        assert res.ok is True
        assert res.output == "validated\n"


def test_run_on_freshness_exception(tmp_path: Path):
    mock = _subproc_mock(stdout="validated\n")
    with patch(
        "aet.validation.evidence.validation_freshness",
        side_effect=RuntimeError("git failure"),
    ), patch("aet.validation.subprocess.run", side_effect=mock):
        res = pre_integration_check("task-1", worktree_dir=tmp_path)
        assert res.decision == RUN
        assert res.ran == ["make", "validate"]
        assert res.ok is True


def test_failed_subprocess_returns_ok_false_and_output(tmp_path: Path):
    mock = _subproc_mock(stdout="syntax error\n", stderr="failed\n", returncode=2)
    with patch(
        "aet.validation.evidence.validation_freshness",
        return_value=FreshnessResult(RUN, "code changed", "h1", "h2", ["foo.py"]),
    ), patch("aet.validation.subprocess.run", side_effect=mock):
        res = pre_integration_check("task-1", worktree_dir=tmp_path)
        assert res.decision == RUN
        assert res.ran == ["make", "validate"]
        assert res.ok is False
        assert "syntax error" in res.output
        assert "failed" in res.output


def test_subprocess_oserror_returns_ok_false(tmp_path: Path):
    mock = _subproc_mock(side_effect=FileNotFoundError("make not found"))
    with patch(
        "aet.validation.evidence.validation_freshness",
        return_value=FreshnessResult(RUN, "code changed", "h1", "h2", ["foo.py"]),
    ), patch("aet.validation.subprocess.run", side_effect=mock):
        res = pre_integration_check("task-1", worktree_dir=tmp_path)
        assert res.decision == RUN
        assert res.ok is False
        assert "make not found" in res.output

"""Tests for the aet sprint intake command (R-13, R-14)."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from aet.backends.git_refs_backend import GitRefsBackend
from aet.cli import sprint as sprint_cmd


def _write_plan(plans_dir: Path, stem: str, blocked_by: list[str] | None = None) -> Path:
    """Write a minimal valid approved plan file."""
    path = plans_dir / f"{stem}.md"
    lines = ["---", f"id: {stem}", "size: S"]
    if blocked_by:
        lines.append("blocked_by:")
        for b in blocked_by:
            lines.append(f"  - {b}")
    lines.extend(
        [
            "---",
            "",
            f"# {stem}",
            "",
            "## Context",
            "PRD: docs/prds/default.md",
            "",
            "## Task List",
            "1. Do something (traces: R-1).",
            "",
            "## Files to Modify",
            "- `src/widget.py` (new)",
            "",
            "## Validation Steps",
            "- [ ] test_widget_creation verifies widget.py",
            "",
            "---",
            "",
            "*Stage: plan-approved*",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_default_prd(plans_dir: Path) -> None:
    prds_dir = plans_dir.parent / "prds"
    prds_dir.mkdir(parents=True, exist_ok=True)
    (prds_dir / "default.md").write_text(
        "# Default PRD\n\n## Requirements\n- **R-1**: default\n", encoding="utf-8"
    )


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "initial"],
        check=True,
    )


def _write_config(root: Path, projections: list[dict] | None = None) -> Path:
    path = root / ".agents" / "aet-config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    config: dict = {}
    if projections is not None:
        config["projections"] = projections
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _seed_queue(root: Path, tasks: list[dict]) -> tuple[Path, Path]:
    queue_file = root / ".agents" / "aet-queue"
    history_file = root / ".agents" / "work-history.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    backend = GitRefsBackend(
        queue_file=str(queue_file), history_file=str(history_file)
    )
    backend.save(tasks)
    return queue_file, history_file


def _read_queue(queue_file: Path, history_file: Path) -> list[dict]:
    return GitRefsBackend(
        queue_file=str(queue_file), history_file=str(history_file)
    ).load()["queue"]


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["gh"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


_real_subprocess_run = subprocess.run


def _gh_side_effect(labels_response: str, issues_response: str):
    def side_effect(cmd, **kwargs):
        if not cmd or cmd[0] != "gh":
            return _real_subprocess_run(cmd, **kwargs)
        if cmd[:3] == ["gh", "label", "list"]:
            return _completed(stdout=labels_response)
        if cmd[:3] == ["gh", "issue", "list"]:
            return _completed(stdout=issues_response)
        if cmd[:3] == ["gh", "issue", "view"]:
            return _completed(stdout='{"labels": [{"name": "aet:sprint"}]}')
        if cmd[:3] == ["gh", "issue", "edit"]:
            return _completed(stdout="")
        raise AssertionError(f"unexpected gh command: {cmd}")

    return side_effect


def _all_aet_labels() -> str:
    return json.dumps(
        [
            {"name": f"aet:{s}"}
            for s in (
                "planned",
                "ready",
                "blocked",
                "in-progress",
                "awaiting-merge",
                "merged",
                "abandoned",
                "failed",
                "quarantined",
                "draft",
                "backlog",
                "sprint",
            )
        ]
    )


class TestSprintIntakeAdmitsUnblockedCandidate(unittest.TestCase):
    """Tracer bullet: an aet:sprint issue with no blockers is admitted."""

    def test_intake_admits_unblocked_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _write_plan(plans_dir, "feat-001")
            _git_init(root)
            config_path = _write_config(
                root, projections=[{"type": "github", "repo": "owner/repo"}]
            )
            history_file = root / ".agents" / "work-history.jsonl"
            queue_file, _ = _seed_queue(root, [])

            issue = {
                "number": 7,
                "body": "<!-- aet-id: feat-001 -->\nPlan file: docs/plans/feat-001.md",
                "labels": [{"name": "aet:sprint"}],
                "state": "open",
            }
            labels_response = _all_aet_labels()
            issues_response = json.dumps([issue])

            with mock.patch("aet.backends.github_backend.subprocess.run") as mock_run:
                mock_run.side_effect = _gh_side_effect(labels_response, issues_response)
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "sprint",
                        "intake",
                        "--queue-file",
                        str(queue_file),
                        "--history-file",
                        str(history_file),
                        "--plans-dir",
                        str(plans_dir),
                        "--config",
                        str(config_path),
                    ],
                ):
                    rc = sprint_cmd.main()

            self.assertEqual(rc, 0)
            data = _read_queue(queue_file, history_file)
            ids = [t["id"] for t in data]
            self.assertIn("feat-001", ids)


class TestSprintIntakeRunsIntakeValidation(unittest.TestCase):
    """The forge door answers to the same admission policy as `sprint add`.

    Regression: `_intake` ran no validation at all. plan_validate was reachable
    only from `_add`, so a plan reachable from an aet:sprint issue entered the
    board without its frontmatter contract, rtrace citations or coverage ever
    being checked — while the identical plan was refused at the other door.
    """

    def _invalid_plan(self, plans_dir: Path, stem: str) -> Path:
        """A footer-approved plan citing an R-id absent from the PRD."""
        path = plans_dir / f"{stem}.md"
        path.write_text(
            "\n".join(
                [
                    "---",
                    f"id: {stem}",
                    "size: S",
                    "---",
                    "",
                    f"# {stem}",
                    "",
                    "## Context",
                    "PRD: docs/prds/default.md",
                    "",
                    "## Task List",
                    "1. Do something (traces: R-1).",
                    "2. Cite a requirement that does not exist (traces: R-99).",
                    "",
                    "## Files to Modify",
                    "- `src/widget.py` (new)",
                    "",
                    "## Validation Steps",
                    "- [ ] test_widget_creation verifies widget.py",
                    "",
                    "---",
                    "",
                    "*Stage: plan-approved*",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_intake_refuses_a_plan_that_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            self._invalid_plan(plans_dir, "feat-bad")
            _git_init(root)
            config_path = _write_config(
                root, projections=[{"type": "github", "repo": "owner/repo"}]
            )
            history_file = root / ".agents" / "work-history.jsonl"
            queue_file, _ = _seed_queue(root, [])

            issue = {
                "number": 9,
                "body": "<!-- aet-id: feat-bad -->\nPlan file: docs/plans/feat-bad.md",
                "labels": [{"name": "aet:sprint"}],
                "state": "open",
            }

            stderr = io.StringIO()
            with mock.patch("aet.backends.github_backend.subprocess.run") as mock_run:
                mock_run.side_effect = _gh_side_effect(
                    _all_aet_labels(), json.dumps([issue])
                )
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "sprint",
                        "intake",
                        "--queue-file",
                        str(queue_file),
                        "--history-file",
                        str(history_file),
                        "--plans-dir",
                        str(plans_dir),
                        "--config",
                        str(config_path),
                    ],
                ):
                    with contextlib.redirect_stderr(stderr):
                        rc = sprint_cmd.main()

            self.assertEqual(rc, 0)
            ids = [t["id"] for t in _read_queue(queue_file, history_file)]
            self.assertNotIn("feat-bad", ids, "invalid plan must not reach the board")
            refusal = stderr.getvalue()
            self.assertIn("rtrace", refusal)
            self.assertIn("R-99", refusal)

    def test_intake_admits_footerless_clean_plan(self):
        """A clean plan with NO _Stage: footer is admitted by sprint intake (R-10)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            plan_path = plans_dir / "feat-clean.md"
            plan_path.write_text(
                "\n".join(
                    [
                        "---",
                        "id: feat-clean",
                        "size: S",
                        "---",
                        "",
                        "# feat-clean",
                        "",
                        "## Context",
                        "PRD: docs/prds/default.md",
                        "",
                        "## Task List",
                        "1. Do something (traces: R-1).",
                        "",
                        "## Files to Modify",
                        "- `src/widget.py` (new)",
                        "",
                        "## Validation Steps",
                        "- [ ] test_widget verifies widget.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            _git_init(root)
            config_path = _write_config(
                root, projections=[{"type": "github", "repo": "owner/repo"}]
            )
            queue_file, history_file = _seed_queue(root, [])
            issue = {
                "number": 42,
                "title": "feat-clean",
                "body": "<!-- aet-id: feat-clean -->\nPlan file: docs/plans/feat-clean.md",
                "labels": [{"name": "aet:sprint"}],
                "state": "open",
            }
            with mock.patch(
                "aet.backends.github_backend.subprocess.run"
            ) as mock_run:
                mock_run.side_effect = _gh_side_effect(
                    _all_aet_labels(), json.dumps([issue])
                )
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "sprint",
                        "intake",
                        "--queue-file",
                        str(queue_file),
                        "--history-file",
                        str(history_file),
                        "--plans-dir",
                        str(plans_dir),
                        "--config",
                        str(config_path),
                    ],
                ):
                    rc = sprint_cmd.main()

            self.assertEqual(rc, 0)
            ids = [t["id"] for t in _read_queue(queue_file, history_file)]
            self.assertIn("feat-clean", ids)


class TestSprintIntakeRefusesBlockedCandidate(unittest.TestCase):
    """A candidate whose blocker is still open is refused, blocker named (R-13)."""

    def test_intake_refuses_blocked_candidate_and_names_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _write_plan(plans_dir, "blocker-001")
            _write_plan(plans_dir, "feat-002", blocked_by=["blocker-001"])
            _git_init(root)
            config_path = _write_config(
                root, projections=[{"type": "github", "repo": "owner/repo"}]
            )
            history_file = root / ".agents" / "work-history.jsonl"
            queue_file, _ = _seed_queue(
                root,
                [
                    {
                        "id": "blocker-001",
                        "title": "blocker",
                        "state": "ready",
                        "blocked_by": [],
                    }
                ],
            )

            issue = {
                "number": 8,
                "body": "<!-- aet-id: feat-002 -->\nPlan file: docs/plans/feat-002.md",
                "labels": [{"name": "aet:sprint"}],
                "state": "open",
            }
            labels_response = _all_aet_labels()
            issues_response = json.dumps([issue])

            with mock.patch("aet.backends.github_backend.subprocess.run") as mock_run:
                mock_run.side_effect = _gh_side_effect(labels_response, issues_response)
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "sprint",
                        "intake",
                        "--queue-file",
                        str(queue_file),
                        "--history-file",
                        str(history_file),
                        "--plans-dir",
                        str(plans_dir),
                        "--config",
                        str(config_path),
                    ],
                ):
                    with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                        with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
                            rc = sprint_cmd.main()

            self.assertEqual(rc, 0)
            data = _read_queue(queue_file, history_file)
            ids = {t["id"] for t in data}
            self.assertNotIn("feat-002", ids)
            output = stdout.getvalue() + stderr.getvalue()
            self.assertIn("blocked by blocker-001", output)


class TestSprintIntakeHaltsOnForgeFailure(unittest.TestCase):
    """A forge read failure retries, then halts and admits nothing (R-14)."""

    def test_intake_halts_on_simulated_403(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _write_plan(plans_dir, "feat-003")
            _git_init(root)
            config_path = _write_config(
                root, projections=[{"type": "github", "repo": "owner/repo"}]
            )
            history_file = root / ".agents" / "work-history.jsonl"
            queue_file, _ = _seed_queue(root, [])

            attempts = []

            def side_effect(cmd, **kwargs):
                if not cmd or cmd[0] != "gh":
                    return _real_subprocess_run(cmd, **kwargs)
                if cmd[:3] == ["gh", "label", "list"]:
                    return _completed(stdout=_all_aet_labels())
                if cmd[:3] == ["gh", "issue", "list"]:
                    attempts.append(cmd)
                    return _completed(
                        returncode=1, stderr="HTTP 403: Forbidden\n"
                    )
                raise AssertionError(f"unexpected gh command: {cmd}")

            with mock.patch("aet.backends.github_backend.subprocess.run") as mock_run:
                mock_run.side_effect = side_effect
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "sprint",
                        "intake",
                        "--queue-file",
                        str(queue_file),
                        "--history-file",
                        str(history_file),
                        "--plans-dir",
                        str(plans_dir),
                        "--config",
                        str(config_path),
                    ],
                ):
                    rc = sprint_cmd.main()

            self.assertEqual(rc, 1)
            data = _read_queue(queue_file, history_file)
            ids = [t["id"] for t in data]
            self.assertEqual(ids, [])
            self.assertGreaterEqual(len(attempts), 1)


class TestSprintIntakeSkipsKnownTasks(unittest.TestCase):
    """Candidates already queued or settled are skipped, not duplicated."""

    def test_intake_skips_already_queued_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _write_plan(plans_dir, "feat-004")
            _git_init(root)
            config_path = _write_config(
                root, projections=[{"type": "github", "repo": "owner/repo"}]
            )
            history_file = root / ".agents" / "work-history.jsonl"
            queue_file, _ = _seed_queue(
                root,
                [
                    {
                        "id": "feat-004",
                        "title": "Already queued",
                        "state": "ready",
                        "blocked_by": [],
                    }
                ],
            )

            issue = {
                "number": 9,
                "body": "<!-- aet-id: feat-004 -->\nPlan file: docs/plans/feat-004.md",
                "labels": [{"name": "aet:sprint"}],
                "state": "open",
            }

            with mock.patch("aet.backends.github_backend.subprocess.run") as mock_run:
                mock_run.side_effect = _gh_side_effect(_all_aet_labels(), json.dumps([issue]))
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "sprint",
                        "intake",
                        "--queue-file",
                        str(queue_file),
                        "--history-file",
                        str(history_file),
                        "--plans-dir",
                        str(plans_dir),
                        "--config",
                        str(config_path),
                    ],
                ):
                    with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                        with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
                            rc = sprint_cmd.main()

            self.assertEqual(rc, 0)
            data = _read_queue(queue_file, history_file)
            self.assertEqual(len(data), 1)
            output = stdout.getvalue() + stderr.getvalue()
            self.assertIn("already in queue", output)

    def test_intake_skips_settled_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _write_plan(plans_dir, "feat-005")
            _git_init(root)
            config_path = _write_config(
                root, projections=[{"type": "github", "repo": "owner/repo"}]
            )
            history_file = root / ".agents" / "work-history.jsonl"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history_file.write_text(
                json.dumps({"id": "feat-005", "state": "merged"}) + "\n",
                encoding="utf-8",
            )
            queue_file, _ = _seed_queue(root, [])

            issue = {
                "number": 10,
                "body": "<!-- aet-id: feat-005 -->\nPlan file: docs/plans/feat-005.md",
                "labels": [{"name": "aet:sprint"}],
                "state": "open",
            }

            with mock.patch("aet.backends.github_backend.subprocess.run") as mock_run:
                mock_run.side_effect = _gh_side_effect(_all_aet_labels(), json.dumps([issue]))
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "sprint",
                        "intake",
                        "--queue-file",
                        str(queue_file),
                        "--history-file",
                        str(history_file),
                        "--plans-dir",
                        str(plans_dir),
                        "--config",
                        str(config_path),
                    ],
                ):
                    with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                        with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
                            rc = sprint_cmd.main()

            self.assertEqual(rc, 0)
            data = _read_queue(queue_file, history_file)
            self.assertEqual(data, [])
            output = stdout.getvalue() + stderr.getvalue()
            self.assertIn("already settled", output)


class TestSprintIntakeEnumeratesOnce(unittest.TestCase):
    """The forge is enumerated exactly once per intake run (R-13)."""

    def test_intake_issues_list_called_once_for_multiple_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _write_plan(plans_dir, "feat-006")
            _write_plan(plans_dir, "feat-007")
            _git_init(root)
            config_path = _write_config(
                root, projections=[{"type": "github", "repo": "owner/repo"}]
            )
            history_file = root / ".agents" / "work-history.jsonl"
            queue_file, _ = _seed_queue(root, [])

            issues = [
                {
                    "number": 11,
                    "body": "<!-- aet-id: feat-006 -->\nPlan file: docs/plans/feat-006.md",
                    "labels": [{"name": "aet:sprint"}],
                    "state": "open",
                },
                {
                    "number": 12,
                    "body": "<!-- aet-id: feat-007 -->\nPlan file: docs/plans/feat-007.md",
                    "labels": [{"name": "aet:sprint"}],
                    "state": "open",
                },
            ]

            list_calls = []

            def side_effect(cmd, **kwargs):
                if not cmd or cmd[0] != "gh":
                    return _real_subprocess_run(cmd, **kwargs)
                if cmd[:3] == ["gh", "label", "list"]:
                    return _completed(stdout=_all_aet_labels())
                if cmd[:3] == ["gh", "issue", "list"]:
                    list_calls.append(cmd)
                    return _completed(stdout=json.dumps(issues))
                if cmd[:3] == ["gh", "issue", "view"]:
                    return _completed(stdout='{"labels": [{"name": "aet:sprint"}]}')
                if cmd[:3] == ["gh", "issue", "edit"]:
                    return _completed(stdout="")
                raise AssertionError(f"unexpected gh command: {cmd}")

            with mock.patch("aet.backends.github_backend.subprocess.run") as mock_run:
                mock_run.side_effect = side_effect
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "sprint",
                        "intake",
                        "--queue-file",
                        str(queue_file),
                        "--history-file",
                        str(history_file),
                        "--plans-dir",
                        str(plans_dir),
                        "--config",
                        str(config_path),
                    ],
                ):
                    rc = sprint_cmd.main()

            self.assertEqual(rc, 0)
            issue_list_calls = [c for c in list_calls if "list" in c]
            self.assertEqual(len(issue_list_calls), 1)
            data = _read_queue(queue_file, history_file)
            ids = {t["id"] for t in data}
            self.assertEqual(ids, {"feat-006", "feat-007"})


if __name__ == "__main__":
    unittest.main()

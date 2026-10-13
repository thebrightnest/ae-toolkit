"""Unit tests for merge train prefix bisect and culprit ejection (ADR-079, R-8)."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aet import train
from aet.backends import create_backend
from aet.backends.factory import DEFAULT_CONFIG_PATH
from aet.cli.aet_state import resolve_task_record


def _get_task_rec(backend, queue_file: str, task_id: str) -> dict:
    task, sealed = resolve_task_record(task_id, queue_file, backend=backend)
    rec = task or sealed
    assert rec is not None, f"Task {task_id} not found in live queue or sealed history"
    return rec


def _init_git_repo(repo_root: str, origin_root: str | None = None) -> None:
    subprocess.run(["git", "init", "-b", "main", repo_root], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo_root, "config", "user.name", "Tester"], check=True)
    subprocess.run(["git", "-C", repo_root, "config", "user.email", "test@example.com"], check=True)
    readme = Path(repo_root) / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-m", "initial commit"], check=True)
    if origin_root:
        subprocess.run(["git", "init", "--bare", "-b", "main", origin_root], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_root, "remote", "add", "origin", origin_root], check=True)
        subprocess.run(["git", "-C", repo_root, "push", "-u", "origin", "main"], check=True, capture_output=True)


def _create_integration_branch(repo_root: str, name: str) -> None:
    subprocess.run(["git", "-C", repo_root, "checkout", "-q", "-b", name], check=True)
    subprocess.run(["git", "-C", repo_root, "push", "-q", "-u", "origin", name], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", f"refs/remotes/origin/{name}", "HEAD"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)


class TestTrainBisect(unittest.TestCase):
    """Unit tests for train.bisect and prefix ejection."""

    def setUp(self):
        self._tmp_repo = tempfile.TemporaryDirectory()
        self._tmp_origin = tempfile.TemporaryDirectory()
        self.repo_root = self._tmp_repo.name
        self.origin_root = self._tmp_origin.name

        self._orig_env = os.environ.copy()
        for k in list(os.environ):
            if k.startswith("AET_"):
                del os.environ[k]

        _init_git_repo(self.repo_root, self.origin_root)
        _create_integration_branch(self.repo_root, "epic-01")

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)
        self._tmp_repo.cleanup()
        self._tmp_origin.cleanup()

    def _stage_dummy_commits(self, count: int, culprit_pos: int | None = None) -> list[str]:
        """Stage `count` sequential commits onto refs/aet/train/epic-01.

        If culprit_pos is provided (1-indexed), commit at culprit_pos creates `fail.txt`.
        """
        commits = []
        base = "origin/epic-01"
        current_parent = base

        for i in range(1, count + 1):
            temp_wt = tempfile.mkdtemp(prefix=f"dummy-task-{i}-")
            try:
                subprocess.run(
                    ["git", "-C", self.repo_root, "worktree", "add", "--detach", temp_wt, current_parent],
                    check=True,
                    capture_output=True,
                )
                file_path = Path(temp_wt) / f"task_{i}.txt"
                file_path.write_text(f"Task {i} content\n", encoding="utf-8")
                if culprit_pos is not None and i >= culprit_pos:
                    fail_file = Path(temp_wt) / "fail.txt"
                    fail_file.write_text(f"Culprit at {culprit_pos}\n", encoding="utf-8")
                subprocess.run(["git", "-C", temp_wt, "add", "."], check=True)
                subprocess.run(["git", "-C", temp_wt, "commit", "-m", f"Integrate task-{i}"], check=True)
                commit_sha = subprocess.run(
                    ["git", "-C", temp_wt, "rev-parse", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                commits.append(commit_sha)
                current_parent = commit_sha
            finally:
                subprocess.run(
                    ["git", "-C", self.repo_root, "worktree", "remove", "--force", temp_wt],
                    capture_output=True,
                )

        subprocess.run(
            ["git", "-C", self.repo_root, "update-ref", "refs/aet/train/epic-01", commits[-1]],
            check=True,
        )
        return commits

    def test_bisect_finds_culprit_at_pos_1_k_and_n_in_log2_runs(self):
        """Culprit at positions 1, k, and n is found in <= ceil(log2 n) runs."""
        n = 3
        max_runs = math.ceil(math.log2(n))

        for pos in [1, 2, 3]:
            with self.subTest(culprit_position=pos):
                commits = self._stage_dummy_commits(n, culprit_pos=pos)
                snapshot = commits[-1]

                counter_file = Path(self.repo_root) / f"val_count_{pos}.log"
                val_script = Path(self.repo_root) / f"val_{pos}.py"
                val_script.write_text(
                    f"import sys, pathlib\n"
                    f"with open({str(counter_file)!r}, 'a') as f:\n"
                    f"    f.write('run\\n')\n"
                    f"if pathlib.Path('fail.txt').exists():\n"
                    f"    sys.stderr.write('FAILURE\\n')\n"
                    f"    sys.exit(1)\n"
                    f"sys.exit(0)\n",
                    encoding="utf-8",
                )

                cmd = f"{sys.executable} {val_script}"
                result = train.bisect(
                    self.repo_root,
                    "epic-01",
                    snapshot,
                    validate_command=cmd,
                )

                self.assertIsNotNone(result, f"Expected culprit for pos={pos}")
                self.assertEqual(result.culprit, commits[pos - 1])
                self.assertEqual(result.k, pos)

                runs_recorded = len(counter_file.read_text(encoding="utf-8").strip().splitlines())
                self.assertLessEqual(
                    runs_recorded,
                    max_runs,
                    f"Pos {pos}: expected at most {max_runs} runs, got {runs_recorded}",
                )

    def test_bisect_returns_none_when_no_failing_prefix(self):
        """When every prefix passes (e.g. transient flake), bisect returns None."""
        n = 3
        commits = self._stage_dummy_commits(n, culprit_pos=None)
        snapshot = commits[-1]

        val_script = Path(self.repo_root) / "val_clean.py"
        val_script.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

        result = train.bisect(
            self.repo_root,
            "epic-01",
            snapshot,
            validate_command=f"{sys.executable} {val_script}",
        )
        self.assertIsNone(result)

    def test_flush_ejects_culprit_and_restacks_clean_tasks(self):
        """A red batch flushes cleanly after bisect ejects the culprit and restacks remaining tasks."""
        # 4 tasks: task-3 fails validation
        tasks = ["task-1", "task-2", "task-3", "task-4"]
        Path(self.repo_root, ".agents").mkdir(parents=True, exist_ok=True)
        queue_file = Path(self.repo_root, ".agents", "aet-queue")
        config_path = Path(self.repo_root, DEFAULT_CONFIG_PATH)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"integration_branch": "epic-01"}), encoding="utf-8")

        backend = create_backend(
            config_path=str(config_path),
            queue_file=str(queue_file),
            history_file=str(Path(self.repo_root, ".agents", "work-history.jsonl")),
        )

        commits = self._stage_dummy_commits(4, culprit_pos=3)
        queue_data = []
        for i, tid in enumerate(tasks, start=1):
            queue_data.append({
                "id": tid,
                "state": "awaiting_merge",
                "train": {
                    "staged_commit": commits[i - 1],
                    "position": i,
                    "branch": "epic-01",
                },
            })
        backend.save(queue_data)

        val_script = Path(self.repo_root) / "validate.py"
        val_script.write_text(
            "import sys, pathlib\n"
            "if pathlib.Path('fail.txt').exists():\n"
            "    sys.stderr.write('Task 3 broke batch validation\\n')\n"
            "    sys.exit(1)\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )

        flush_res = train.flush(
            self.repo_root,
            "epic-01",
            backend=backend,
            validate_command=f"{sys.executable} {val_script}",
        )

        self.assertTrue(flush_res.ok)
        self.assertEqual(flush_res.status, "green")
        self.assertEqual(set(flush_res.tasks_flushed), {"task-1", "task-2", "task-4"})

        # Check queue states
        t1 = _get_task_rec(backend, str(queue_file), "task-1")
        t2 = _get_task_rec(backend, str(queue_file), "task-2")
        t3 = _get_task_rec(backend, str(queue_file), "task-3")
        t4 = _get_task_rec(backend, str(queue_file), "task-4")

        self.assertEqual(t1["state"], "merged")
        self.assertEqual(t2["state"], "merged")
        self.assertEqual(t4["state"], "merged")

        # Culprit task-3 stays awaiting_merge with batch_validation diagnostics
        self.assertEqual(t3["state"], "awaiting_merge")
        self.assertIsNone(t3.get("train"))
        self.assertIsNotNone(t3.get("conflict_diagnostics"))
        self.assertEqual(t3["conflict_diagnostics"]["reason"], "batch_validation")
        self.assertIn("Task 3 broke batch validation", t3["conflict_diagnostics"]["stderr_tail"])

    def test_flush_restack_conflict_ejection(self):
        """When a task cannot cleanly re-stack after culprit ejection, it is ejected with restack_conflict."""
        # Task 1: modifies file a.txt
        # Task 2: modifies shared.txt (Culprit: fails validation)
        # Task 3: modifies shared.txt based on Task 2 (Will conflict when Task 2 is removed)
        # Task 4: modifies file c.txt (Applies cleanly)
        base = "origin/epic-01"
        current_parent = base
        commits = []

        # Commit 1
        t1_wt = tempfile.mkdtemp(prefix="task-1-")
        try:
            subprocess.run(
                ["git", "-C", self.repo_root, "worktree", "add", "--detach", t1_wt, current_parent],
                check=True,
                capture_output=True,
            )
            (Path(t1_wt) / "a.txt").write_text("file a\n")
            subprocess.run(["git", "-C", t1_wt, "add", "."], check=True)
            subprocess.run(["git", "-C", t1_wt, "commit", "-m", "Integrate task-1"], check=True)
            c1 = subprocess.run(
                ["git", "-C", t1_wt, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
            ).stdout.strip()
            commits.append(c1)
            current_parent = c1
        finally:
            subprocess.run(["git", "-C", self.repo_root, "worktree", "remove", "--force", t1_wt], capture_output=True)

        # Commit 2 (Culprit)
        t2_wt = tempfile.mkdtemp(prefix="task-2-")
        try:
            subprocess.run(
                ["git", "-C", self.repo_root, "worktree", "add", "--detach", t2_wt, current_parent],
                check=True,
                capture_output=True,
            )
            (Path(t2_wt) / "shared.txt").write_text("line from task 2\n")
            (Path(t2_wt) / "fail.txt").write_text("fail\n")
            subprocess.run(["git", "-C", t2_wt, "add", "."], check=True)
            subprocess.run(["git", "-C", t2_wt, "commit", "-m", "Integrate task-2"], check=True)
            c2 = subprocess.run(
                ["git", "-C", t2_wt, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
            ).stdout.strip()
            commits.append(c2)
            current_parent = c2
        finally:
            subprocess.run(["git", "-C", self.repo_root, "worktree", "remove", "--force", t2_wt], capture_output=True)

        # Commit 3 (Modifies shared.txt on top of Commit 2)
        t3_wt = tempfile.mkdtemp(prefix="task-3-")
        try:
            subprocess.run(
                ["git", "-C", self.repo_root, "worktree", "add", "--detach", t3_wt, current_parent],
                check=True,
                capture_output=True,
            )
            (Path(t3_wt) / "shared.txt").write_text("line from task 2\nand line from task 3\n")
            subprocess.run(["git", "-C", t3_wt, "add", "."], check=True)
            subprocess.run(["git", "-C", t3_wt, "commit", "-m", "Integrate task-3"], check=True)
            c3 = subprocess.run(
                ["git", "-C", t3_wt, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
            ).stdout.strip()
            commits.append(c3)
            current_parent = c3
        finally:
            subprocess.run(["git", "-C", self.repo_root, "worktree", "remove", "--force", t3_wt], capture_output=True)

        # Commit 4 (Modifies c.txt)
        t4_wt = tempfile.mkdtemp(prefix="task-4-")
        try:
            subprocess.run(
                ["git", "-C", self.repo_root, "worktree", "add", "--detach", t4_wt, current_parent],
                check=True,
                capture_output=True,
            )
            (Path(t4_wt) / "c.txt").write_text("file c\n")
            subprocess.run(["git", "-C", t4_wt, "add", "."], check=True)
            subprocess.run(["git", "-C", t4_wt, "commit", "-m", "Integrate task-4"], check=True)
            c4 = subprocess.run(
                ["git", "-C", t4_wt, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
            ).stdout.strip()
            commits.append(c4)
            current_parent = c4
        finally:
            subprocess.run(["git", "-C", self.repo_root, "worktree", "remove", "--force", t4_wt], capture_output=True)

        subprocess.run(["git", "-C", self.repo_root, "update-ref", "refs/aet/train/epic-01", commits[-1]], check=True)

        Path(self.repo_root, ".agents").mkdir(parents=True, exist_ok=True)
        queue_file = Path(self.repo_root, ".agents", "aet-queue")
        config_path = Path(self.repo_root, DEFAULT_CONFIG_PATH)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"integration_branch": "epic-01"}), encoding="utf-8")

        backend = create_backend(
            config_path=str(config_path),
            queue_file=str(queue_file),
            history_file=str(Path(self.repo_root, ".agents", "work-history.jsonl")),
        )
        tasks = ["task-1", "task-2", "task-3", "task-4"]
        queue_data = []
        for i, tid in enumerate(tasks, start=1):
            queue_data.append({
                "id": tid,
                "state": "awaiting_merge",
                "train": {
                    "staged_commit": commits[i - 1],
                    "position": i,
                    "branch": "epic-01",
                },
            })
        backend.save(queue_data)

        val_script = Path(self.repo_root) / "validate.py"
        val_script.write_text(
            "import sys, pathlib\n"
            "if pathlib.Path('fail.txt').exists():\n"
            "    sys.exit(1)\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )

        flush_res = train.flush(
            self.repo_root,
            "epic-01",
            backend=backend,
            validate_command=f"{sys.executable} {val_script}",
        )

        self.assertTrue(flush_res.ok)
        self.assertEqual(flush_res.status, "green")
        self.assertEqual(set(flush_res.tasks_flushed), {"task-1", "task-4"})

        t1 = _get_task_rec(backend, str(queue_file), "task-1")
        t2 = _get_task_rec(backend, str(queue_file), "task-2")
        t3 = _get_task_rec(backend, str(queue_file), "task-3")
        t4 = _get_task_rec(backend, str(queue_file), "task-4")

        self.assertEqual(t1["state"], "merged")
        self.assertEqual(t4["state"], "merged")

        # task-2 was culprit: batch_validation
        self.assertEqual(t2["state"], "awaiting_merge")
        self.assertEqual(t2["conflict_diagnostics"]["reason"], "batch_validation")

        # task-3 failed to restack: restack_conflict
        self.assertEqual(t3["state"], "awaiting_merge")
        self.assertEqual(t3["conflict_diagnostics"]["reason"], "restack_conflict")
        self.assertIn("shared.txt", t3["conflict_diagnostics"]["conflicting_files"])

    def test_flush_flake_path_re_runs_and_halts_if_red(self):
        """Flake path: if bisect finds no failing prefix, re-runs full snapshot; if red again, halts fail-closed."""
        commits = self._stage_dummy_commits(2, culprit_pos=None)
        Path(self.repo_root, ".agents").mkdir(parents=True, exist_ok=True)
        queue_file = Path(self.repo_root, ".agents", "aet-queue")
        config_path = Path(self.repo_root, DEFAULT_CONFIG_PATH)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"integration_branch": "epic-01"}), encoding="utf-8")

        backend = create_backend(
            config_path=str(config_path),
            queue_file=str(queue_file),
            history_file=str(Path(self.repo_root, ".agents", "work-history.jsonl")),
        )
        queue_data = [
            {
                "id": "task-1",
                "state": "awaiting_merge",
                "train": {"staged_commit": commits[0], "position": 1, "branch": "epic-01"},
            },
            {
                "id": "task-2",
                "state": "awaiting_merge",
                "train": {"staged_commit": commits[1], "position": 2, "branch": "epic-01"},
            },
        ]
        backend.save(queue_data)

        # Validation script: fails ONLY on the full snapshot (has both task_1.txt and task_2.txt)
        val_script = Path(self.repo_root) / "val_flake.py"
        val_script.write_text(
            "import sys, pathlib\n"
            "if pathlib.Path('task_1.txt').exists() and pathlib.Path('task_2.txt').exists():\n"
            "    sys.exit(1)\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )

        # Initial flush fails on snapshot (task-1 + task-2).
        # Bisect tests prefix 1 (task-1 only) -> passes!
        # Prefix 2 is the full snapshot, but bisect candidate low=high=2 tests 2 -> fails!
        # Wait, to test flake where bisect returns None:
        # A script that fails on first run, but bisect runs pass because bisect doesn't fail, or state-based:
        counter_file = Path(self.repo_root) / "flake_counter.txt"
        val_script.write_text(
            f"import sys, pathlib\n"
            f"c = 0\n"
            f"p = pathlib.Path({str(counter_file)!r})\n"
            f"if p.exists():\n"
            f"    c = int(p.read_text().strip())\n"
            f"c += 1\n"
            f"p.write_text(str(c))\n"
            f"# Fail on 1st run (initial flush) and 4th run (retry after bisect returns None)\n"
            f"# During bisect (runs 2 and 3), pass all prefixes!\n"
            f"if c in (1, 4):\n"
            f"    sys.stderr.write('Flake or red\\n')\n"
            f"    sys.exit(1)\n"
            f"sys.exit(0)\n",
            encoding="utf-8",
        )

        flush_res = train.flush(
            self.repo_root,
            "epic-01",
            backend=backend,
            validate_command=f"{sys.executable} {val_script}",
        )

        # Re-run was red -> halt
        self.assertFalse(flush_res.ok)
        self.assertEqual(flush_res.status, "halt")


if __name__ == "__main__":
    unittest.main()

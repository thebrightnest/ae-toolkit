"""Unit and integration tests for merge train staging ref and flush (Tasks 1, 3, 4)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from aet import evidence, telemetry, train
from aet.backends import create_backend

pytestmark = pytest.mark.xdist_group("git-repo")


def _init_repo(repo_root: str, origin_root: str, branch: str = "main") -> None:
    subprocess.run(["git", "init", "--bare", "-q", origin_root], check=True)
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(["git", "-C", repo_root, "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", repo_root, "config", "user.name", "Test User"], check=True)
    Path(repo_root, "README.md").write_text("# Repo\n", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", repo_root, "branch", "-M", branch], check=True)
    subprocess.run(["git", "-C", repo_root, "remote", "add", "origin", origin_root], check=True)
    subprocess.run(["git", "-C", repo_root, "push", "-q", "-u", "origin", branch], check=True)
    subprocess.run(["git", "-C", repo_root, "update-ref", f"refs/remotes/origin/{branch}", "HEAD"], check=True)


class TestTrainRefHelpers(unittest.TestCase):
    def test_train_ref(self):
        self.assertEqual(train.train_ref("main"), "refs/aet/train/main")
        self.assertEqual(train.train_ref("epic-01"), "refs/aet/train/epic-01")

    def test_train_tip_fallback_to_origin_or_local(self):
        with tempfile.TemporaryDirectory() as origin_dir, tempfile.TemporaryDirectory() as repo_dir:
            _init_repo(repo_dir, origin_dir, "main")
            # When no staging ref exists, tip should be origin/main
            self.assertEqual(train.train_tip(repo_dir, "main"), "origin/main")

            # When staging ref is created, tip should be refs/aet/train/main
            head_commit = subprocess.check_output(
                ["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True
            ).strip()
            train.update_train_ref(repo_dir, "main", head_commit, old_commit="0" * 40)
            self.assertEqual(train.train_tip(repo_dir, "main"), "refs/aet/train/main")

    def test_staging_ref_cas_rejects_concurrent_update(self):
        with tempfile.TemporaryDirectory() as origin_dir, tempfile.TemporaryDirectory() as repo_dir:
            _init_repo(repo_dir, origin_dir, "main")
            c1 = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()
            Path(repo_dir, "file.txt").write_text("c2", encoding="utf-8")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "c2"], check=True)
            c2 = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()

            # First update with 0*40 succeeds
            ok = train.update_train_ref(repo_dir, "main", c1, old_commit="0" * 40)
            self.assertTrue(ok)

            # Update with wrong expected old commit fails CAS
            wrong_old = "1" * 40
            ok_wrong = train.update_train_ref(repo_dir, "main", c2, old_commit=wrong_old)
            self.assertFalse(ok_wrong)

            # Update with matching expected old commit succeeds
            ok_match = train.update_train_ref(repo_dir, "main", c2, old_commit=c1)
            self.assertTrue(ok_match)

    def test_rebuild_from_records(self):
        with tempfile.TemporaryDirectory() as origin_dir, tempfile.TemporaryDirectory() as repo_dir:
            _init_repo(repo_dir, origin_dir, "main")
            c1 = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()
            queue = [
                {
                    "id": "task-1",
                    "state": "awaiting_merge",
                    "train": {
                        "branch": "main",
                        "position": 1,
                        "staged_commit": c1,
                        "staged_at": "2026-10-13T10:00:00Z",
                    },
                }
            ]
            rebuilt_commit = train.rebuild_from_records(repo_dir, "main", queue=queue)
            self.assertEqual(rebuilt_commit, c1)

            ref_commit = subprocess.check_output(
                ["git", "-C", repo_dir, "rev-parse", "refs/aet/train/main"], text=True
            ).strip()
            self.assertEqual(ref_commit, c1)


class TestTrainFlush(unittest.TestCase):
    def test_green_flush_fast_forwards_and_records_verdict(self):
        with tempfile.TemporaryDirectory() as origin_dir, tempfile.TemporaryDirectory() as repo_dir:
            _init_repo(repo_dir, origin_dir, "main")
            queue_file = os.path.join(repo_dir, ".agents", "aet-queue")
            os.makedirs(os.path.join(repo_dir, ".agents"), exist_ok=True)
            backend = create_backend(
                config_path=os.path.join(repo_dir, ".agents", "aet-config.json"),
                queue_file=queue_file,
                history_file=os.path.join(repo_dir, ".agents", "work-history.jsonl"),
            )

            # Make a staged commit
            Path(repo_dir, "task1.txt").write_text("task1 content", encoding="utf-8")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "task 1 commit"], check=True)
            c1 = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()
            # Reset main branch back to initial so main is behind c1
            subprocess.run(["git", "-C", repo_dir, "reset", "--hard", "HEAD~1"], check=True)

            # Stage c1 on train
            train.update_train_ref(repo_dir, "main", c1, old_commit="0" * 40)
            queue = [
                {
                    "id": "task-1",
                    "state": "awaiting_merge",
                    "train": {
                        "branch": "main",
                        "position": 1,
                        "staged_commit": c1,
                        "staged_at": "2026-10-13T10:00:00Z",
                    },
                }
            ]
            backend.save(queue)

            result = train.flush(
                repo_dir,
                "main",
                backend=backend,
                validate_command=["true"],
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.status, "green")
            self.assertEqual(result.tasks_flushed, ["task-1"])

            # Verify main branch fast-forwarded to c1
            main_commit = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "main"], text=True).strip()
            self.assertEqual(main_commit, c1)

            # Verify origin/main was pushed
            origin_commit = subprocess.check_output(
                ["git", "-C", repo_dir, "rev-parse", "refs/remotes/origin/main"], text=True
            ).strip()
            self.assertEqual(origin_commit, c1)

            # Verify task-1 transitioned to merged with merge_commit
            saved_queue = backend.load()["queue"]
            self.assertEqual(saved_queue, [])
            sealed = backend.read_sealed("task-1")
            self.assertIsNotNone(sealed)
            self.assertEqual(sealed["state"], "merged")
            self.assertEqual(sealed["merge_commit"], c1)
            self.assertNotIn("train", sealed)

            # Verify staging ref deleted
            res = subprocess.run(
                ["git", "-C", repo_dir, "rev-parse", "--verify", "refs/aet/train/main"],
                capture_output=True,
            )
            self.assertNotEqual(res.returncode, 0)

            # Verify batch verdict recorded
            slug = telemetry.derive_project_slug(repo_dir)
            batch_path = evidence.resolve_verdict_path("main", "batch", project_slug=slug)
            self.assertTrue(batch_path.exists())
            verdicts = json.loads(batch_path.read_text(encoding="utf-8"))
            self.assertEqual(verdicts[-1]["verdict"], "pass")
            self.assertEqual(verdicts[-1]["task_ids"], ["task-1"])

    def test_tasks_staged_after_snapshot_remain_staged(self):
        with tempfile.TemporaryDirectory() as origin_dir, tempfile.TemporaryDirectory() as repo_dir:
            _init_repo(repo_dir, origin_dir, "main")
            queue_file = os.path.join(repo_dir, ".agents", "aet-queue")
            os.makedirs(os.path.join(repo_dir, ".agents"), exist_ok=True)
            backend = create_backend(
                config_path=os.path.join(repo_dir, ".agents", "aet-config.json"),
                queue_file=queue_file,
                history_file=os.path.join(repo_dir, ".agents", "work-history.jsonl"),
            )

            Path(repo_dir, "t1.txt").write_text("t1", encoding="utf-8")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "t1"], check=True)
            c1 = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()

            Path(repo_dir, "t2.txt").write_text("t2", encoding="utf-8")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "t2"], check=True)
            c2 = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()

            # Reset main back to initial
            subprocess.run(["git", "-C", repo_dir, "reset", "--hard", "HEAD~2"], check=True)

            # Stage task 1
            train.update_train_ref(repo_dir, "main", c1, old_commit="0" * 40)
            queue = [
                {
                    "id": "task-1",
                    "state": "awaiting_merge",
                    "train": {
                        "branch": "main",
                        "position": 1,
                        "staged_commit": c1,
                        "staged_at": "2026-10-13T10:00:00Z",
                    },
                }
            ]
            backend.save(queue)

            # Flush with validate_command callback/hook or script
            hook_script = Path(repo_dir, "hook.py")
            cfg_path = os.path.join(repo_dir, ".agents", "aet-config.json")
            hist_path = os.path.join(repo_dir, ".agents", "work-history.jsonl")
            hook_body = (
                "import subprocess, os\n"
                "from aet.backends.factory import create_backend\n"
                f"subprocess.run(['git', '-C', {repr(repo_dir)}, 'update-ref', "
                f"'refs/aet/train/main', {repr(c2)}, {repr(c1)}], check=True)\n"
                f"b = create_backend(config_path={repr(cfg_path)}, "
                f"queue_file={repr(queue_file)}, history_file={repr(hist_path)})\n"
                "q = b.load()['queue']\n"
                f"q.append({{'id': 'task-2', 'state': 'awaiting_merge', "
                f"'train': {{'branch': 'main', 'position': 2, 'staged_commit': {repr(c2)}, "
                f"'staged_at': '2026-10-13T10:05:00Z'}}}})\n"
                "b.save(q)\n"
            )
            hook_script.write_text(hook_body, encoding="utf-8")
            result = train.flush(
                repo_dir,
                "main",
                backend=backend,
                validate_command=[sys.executable, str(hook_script)],
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.tasks_flushed, ["task-1"])

            # Verify task-1 merged and sealed, but task-2 still in active queue and staged
            saved_queue = backend.load()["queue"]
            self.assertEqual(len(saved_queue), 1)
            t2 = saved_queue[0]
            self.assertEqual(t2["id"], "task-2")
            self.assertEqual(t2["state"], "awaiting_merge")
            self.assertIn("train", t2)
            self.assertEqual(t2["train"]["staged_commit"], c2)

            sealed_t1 = backend.read_sealed("task-1")
            self.assertIsNotNone(sealed_t1)
            self.assertEqual(sealed_t1["state"], "merged")

            # Staging ref still points to c2!
            staging_tip = subprocess.check_output(
                ["git", "-C", repo_dir, "rev-parse", "refs/aet/train/main"], text=True
            ).strip()
            self.assertEqual(staging_tip, c2)

    def test_red_flush_fail_closed(self):
        with tempfile.TemporaryDirectory() as origin_dir, tempfile.TemporaryDirectory() as repo_dir:
            _init_repo(repo_dir, origin_dir, "main")
            queue_file = os.path.join(repo_dir, ".agents", "aet-queue")
            os.makedirs(os.path.join(repo_dir, ".agents"), exist_ok=True)
            backend = create_backend(
                config_path=os.path.join(repo_dir, ".agents", "aet-config.json"),
                queue_file=queue_file,
                history_file=os.path.join(repo_dir, ".agents", "work-history.jsonl"),
            )

            Path(repo_dir, "task1.txt").write_text("task1 content", encoding="utf-8")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "task 1 commit"], check=True)
            c1 = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()
            subprocess.run(["git", "-C", repo_dir, "reset", "--hard", "HEAD~1"], check=True)
            initial_main = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "main"], text=True).strip()

            train.update_train_ref(repo_dir, "main", c1, old_commit="0" * 40)
            queue = [
                {
                    "id": "task-1",
                    "state": "awaiting_merge",
                    "train": {
                        "branch": "main",
                        "position": 1,
                        "staged_commit": c1,
                        "staged_at": "2026-10-13T10:00:00Z",
                    },
                }
            ]
            backend.save(queue)

            result = train.flush(
                repo_dir,
                "main",
                backend=backend,
                validate_command=["false"],  # Fails!
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.status, "empty")

            # Main unmoved
            curr_main = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "main"], text=True).strip()
            self.assertEqual(curr_main, initial_main)

            # Task remains awaiting_merge with culprit ejected (train marker cleared)
            saved_queue = backend.load()["queue"]
            t1 = saved_queue[0]
            self.assertEqual(t1["state"], "awaiting_merge")
            self.assertNotIn("train", t1)
            self.assertEqual(t1["conflict_diagnostics"]["reason"], "batch_validation")

    def test_red_flush_flake_halts_fail_closed(self):
        with tempfile.TemporaryDirectory() as origin_dir, tempfile.TemporaryDirectory() as repo_dir:
            _init_repo(repo_dir, origin_dir, "main")
            queue_file = os.path.join(repo_dir, ".agents", "aet-queue")
            os.makedirs(os.path.join(repo_dir, ".agents"), exist_ok=True)
            backend = create_backend(
                config_path=os.path.join(repo_dir, ".agents", "aet-config.json"),
                queue_file=queue_file,
                history_file=os.path.join(repo_dir, ".agents", "work-history.jsonl"),
            )

            Path(repo_dir, "task1.txt").write_text("task1 content", encoding="utf-8")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "task 1 commit"], check=True)
            c1 = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()
            subprocess.run(["git", "-C", repo_dir, "reset", "--hard", "HEAD~1"], check=True)

            train.update_train_ref(repo_dir, "main", c1, old_commit="0" * 40)
            queue = [
                {
                    "id": "task-1",
                    "state": "awaiting_merge",
                    "train": {
                        "branch": "main",
                        "position": 1,
                        "staged_commit": c1,
                        "staged_at": "2026-10-13T10:00:00Z",
                    },
                }
            ]
            backend.save(queue)

            from unittest.mock import patch
            with patch("aet.train.bisect", return_value=None):
                result = train.flush(
                    repo_dir,
                    "main",
                    backend=backend,
                    validate_command=["false"],
                )
            self.assertFalse(result.ok)
            self.assertEqual(result.status, "halt")

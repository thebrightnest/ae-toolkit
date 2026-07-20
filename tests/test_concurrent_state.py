"""Concurrent safety tests for the aet-state queue layer.

These tests exercise real multiprocess load against temp queue files to
verify that the state layer's locked, atomic read-modify-write cycles never
lose updates and never expose a partial JSON file.
"""

import importlib.machinery
import importlib.util
import json
import multiprocessing
import tempfile
import time
import unittest
from pathlib import Path

from aet import queue as queue_lib

_AET_STATE_PY = Path(__file__).parent.parent / "src" / "aet" / "cli" / "aet-state.py"
_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)


# Multiprocessing start method on macOS is 'spawn', so worker functions must be
# importable and self-contained. They re-import aet_state internally.


def _worker_set_stages(queue_path: str, task_id: str, stages: list[str]) -> None:
    mod = _load_aet_state()
    for stage in stages:
        args = mod.argparse.Namespace(
            command="set-stage",
            task_id=task_id,
            stage=stage,
            queue=queue_path,
            dry_run=False,
        )
        rc = mod.cmd_set_stage(args)
        if rc != 0:
            raise RuntimeError(f"set-stage failed for {task_id} -> {stage}")


def _worker_reader(queue_path: str, stop: multiprocessing.Event, result_path: str) -> None:
    reads = 0
    errors: list[str] = []
    while not stop.is_set():
        try:
            with open(queue_path, "r", encoding="utf-8") as f:
                json.load(f)
            reads += 1
        except json.JSONDecodeError as e:
            errors.append(str(e))
            break
        except FileNotFoundError:
            # Writer may not have created the file yet.
            time.sleep(0.001)
    Path(result_path).write_text(json.dumps({"reads": reads, "errors": errors}), encoding="utf-8")


def _worker_writer(queue_path: str, task_id: str, stages: list[str], done: multiprocessing.Event) -> None:
    mod = _load_aet_state()
    for stage in stages:
        args = mod.argparse.Namespace(
            command="set-stage",
            task_id=task_id,
            stage=stage,
            queue=queue_path,
            dry_run=False,
        )
        mod.cmd_set_stage(args)
    done.set()


def _load_aet_state():
    """Re-import aet-state inside a spawned child process."""
    spec = importlib.util.spec_from_loader(
        "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestQueueLock(unittest.TestCase):
    def test_queue_lock_reentrant_same_process(self):
        """queue_lock can be nested in the same process without deadlocking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = str(Path(tmpdir) / "work-queue.json")
            Path(queue_path).write_text(json.dumps({"tasks": []}), encoding="utf-8")

            with queue_lib.queue_lock(queue_path):
                with queue_lib.queue_lock(queue_path):
                    tasks = queue_lib.read_queue(queue_path)
                    self.assertEqual(tasks, [])


class TestSetStageBackendRouting(unittest.TestCase):
    def test_set_stage_routes_through_backend_and_preserves_envelope(self):
        """set-stage uses the backend, so dict-wrapper metadata survives."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "work-queue.json"
            queue_path.write_text(
                json.dumps(
                    {
                        "source_prd": "docs/prds/example.md",
                        "queue_updated_at": "2026-07-09T00:00:00Z",
                        "tasks": [
                            {
                                "id": "t1",
                                "state": "in_progress",
                                "stage": "plan-approved",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            args = aet_state.argparse.Namespace(
                command="set-stage",
                task_id="t1",
                stage="implemented",
                queue=str(queue_path),
                dry_run=False,
            )
            rc = aet_state.cmd_set_stage(args)
            self.assertEqual(rc, 0)

            with open(queue_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertIsInstance(data, dict)
            self.assertEqual(data.get("source_prd"), "docs/prds/example.md")
            self.assertIn("queue_updated_at", data)
            task = data["tasks"][0]
            self.assertEqual(task["stage"], "implemented")
            self.assertEqual(task["history"][0]["to"], "implemented")


class TestConcurrentState(unittest.TestCase):
    def test_parallel_set_stage_no_lost_updates(self):
        """Concurrent set-stage on distinct tasks never loses a history entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "work-queue.json"
            tasks = [
                {"id": f"t{i}", "state": "in_progress", "stage": "plan-approved"}
                for i in range(4)
            ]
            queue_path.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")

            processes = []
            for i in range(4):
                task_id = f"t{i}"
                stages = [f"t{i}-s{j}" for j in range(10)]
                p = multiprocessing.Process(
                    target=_worker_set_stages, args=(str(queue_path), task_id, stages)
                )
                processes.append(p)
                p.start()

            for p in processes:
                p.join(timeout=60)
                self.assertEqual(p.exitcode, 0, "worker process exited with error")

            with open(queue_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            by_id = {t["id"]: t for t in data["tasks"]}
            for i in range(4):
                task_id = f"t{i}"
                task = by_id[task_id]
                history_tos = {h["to"] for h in task.get("history", [])}
                expected = {f"t{i}-s{j}" for j in range(10)}
                self.assertEqual(history_tos, expected)

    def test_parallel_transitions_valid_json_every_read(self):
        """A reader never sees a partially-written queue file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "work-queue.json"
            queue_path.write_text(
                json.dumps(
                    {"tasks": [{"id": "t1", "state": "in_progress", "stage": "start"}]}
                ),
                encoding="utf-8",
            )

            stop = multiprocessing.Event()
            result_path = str(Path(tmpdir) / "reader-result.json")
            done = multiprocessing.Event()

            reader = multiprocessing.Process(
                target=_worker_reader, args=(str(queue_path), stop, result_path)
            )
            reader.start()

            stages = [f"s{i}" for i in range(50)]
            writer = multiprocessing.Process(
                target=_worker_writer,
                args=(str(queue_path), "t1", stages, done),
            )
            writer.start()

            done.wait(timeout=60)
            time.sleep(0.05)  # Let reader observe a few more post-write states.
            stop.set()
            reader.join(timeout=10)
            writer.join(timeout=10)

            result = json.loads(Path(result_path).read_text(encoding="utf-8"))
            reads = result["reads"]
            errors = result["errors"]
            self.assertGreater(reads, 0, "reader did not observe any valid reads")
            self.assertEqual(errors, [], f"reader encountered invalid JSON: {errors}")


if __name__ == "__main__":
    unittest.main()

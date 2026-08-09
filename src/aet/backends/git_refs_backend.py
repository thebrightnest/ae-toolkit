"""Git-refs backend for the aet-work queue.

Each live task record is stored as a JSON blob addressed by a git ref under
``refs/aet/tasks/<task-id>``. Queue envelope metadata (``source_prd``,
``queue_updated_at``, ``schema_version``, …) lives at ``refs/aet/meta/queue``.
Settled history is left in the append-only ``work-history.jsonl`` file, exactly
as the JSON backend does — this backend is storage-only; state legality stays in
``aet-state``.

Ref updates are atomic under git's own ref locks. A multi-task ``save`` writes
per-task refs and skips tasks whose blob is unchanged versus what was loaded, so
concurrent writers touching *different* tasks never clobber each other. Nothing
here pushes ``refs/aet/*``: the backend is local-only by default.

The envelope carries a ``schema_version`` field (ADR-055).  A previous chained
``content_hash`` over the task-ref set has been removed: a chain over a set is
non-commutative, so independent writers produced irreconcilable conflicts by
construction.  Hand-edited refs are therefore no longer a hard failure; the
backend reads the live refs as ground truth.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from aet.backends.base import TaskBackend
from aet.queue import read_history

TASKS_REF_PREFIX = "refs/aet/tasks/"
ENVELOPE_REF = "refs/aet/meta/queue"
ENVELOPE_SCHEMA_VERSION = 1

# Git's null object id: used as the ``oldvalue`` of a compare-and-swap create
# so a fresh task ref is only written when it does not already exist.
_NULL_OID = "0" * 40


def _canonical_json(value: Any) -> bytes:
    """Serialize ``value`` to stable UTF-8 JSON bytes for content addressing."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


class GitRefsBackend(TaskBackend):
    """Git-native implementation of the task backend interface."""

    def __init__(
        self,
        queue_file: str = ".agents/work-queue.json",
        history_file: str = ".agents/work-history.jsonl",
    ) -> None:
        self.queue_file = queue_file
        self.history_file = history_file
        queue_dir = Path(queue_file).resolve().parent
        self.repo_root = self._discover_repo_root(queue_dir)
        # Blob SHAs observed at the most recent ``load`` (or last successful
        # ``save``), keyed by task id. Drives the skip-unchanged optimization and
        # the compare-and-swap ``update-ref`` that makes disjoint concurrent
        # writers safe.
        self._loaded_shas: dict[str, str] = {}
        self._envelope: dict[str, Any] = {}

    @staticmethod
    def _discover_repo_root(queue_dir: Path) -> str:
        """Return the git work-tree root containing ``queue_dir``.

        Raises ``RuntimeError`` when ``queue_dir`` is not inside a git
        repository (or git is unavailable), so misconfiguration fails fast and
        loudly rather than writing refs into the wrong place.
        """
        result = subprocess.run(
            ["git", "-C", str(queue_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "GitRefsBackend requires the queue path to live inside a git "
                f"repository; {queue_dir} is not inside a git repository"
            )
        return result.stdout.strip()

    # -- git plumbing helpers -------------------------------------------------

    def _git(
        self, *args: str, input: bytes | None = None
    ) -> subprocess.CompletedProcess:
        """Run git in the repo root and return the completed (binary) process."""
        return subprocess.run(
            ["git", "-C", self.repo_root, *args],
            input=input,
            capture_output=True,
        )

    def _write_blob(self, data: bytes) -> str:
        result = self._git("hash-object", "-w", "--stdin", input=data)
        result.check_returncode()
        return result.stdout.decode().strip()

    def _read_blob(self, sha: str) -> bytes:
        result = self._git("cat-file", "-p", sha)
        result.check_returncode()
        return result.stdout

    def _ref_sha(self, ref: str) -> str | None:
        """Return the object id ``ref`` points to, or ``None`` if it is absent."""
        result = self._git("rev-parse", "--verify", "-q", ref)
        if result.returncode != 0:
            return None
        return result.stdout.decode().strip()

    def _list_task_refs(self) -> list[str]:
        result = self._git(
            "for-each-ref", "--format=%(refname)", TASKS_REF_PREFIX
        )
        result.check_returncode()
        return [line for line in result.stdout.decode().splitlines() if line]

    def _history_path(self) -> str:
        path = Path(self.history_file)
        if path.is_absolute():
            return str(path)
        return str(Path(self.repo_root) / path)

    def _resolve_history(self, history_file: str) -> str:
        """Resolve a caller-supplied history path against the repo root.

        ``aet-state`` hands ``seal`` the backend's own ``history_file``, which
        may be relative to the repo root (the default) or absolute (for example
        a second worktree). Git plumbing always runs from ``repo_root``, so a
        relative path must be anchored there rather than to the process cwd.
        """
        path = Path(history_file)
        if path.is_absolute():
            return str(path)
        return str(Path(self.repo_root) / path)

    # -- TaskBackend interface ------------------------------------------------

    def load(self, verify: bool = True) -> dict[str, Any]:
        """Return queue (from refs) and settled history (from JSONL).

        ``verify`` is retained for interface compatibility but is ignored: the
        git-refs backend no longer enforces a chained content hash (ADR-055).
        The live refs are read as ground truth.
        """
        queue: list[dict[str, Any]] = []
        loaded_shas: dict[str, str] = {}
        for ref in self._list_task_refs():
            sha = self._ref_sha(ref)
            if sha is None:
                continue
            task_id = ref[len(TASKS_REF_PREFIX) :]
            try:
                task = json.loads(self._read_blob(sha))
            except (json.JSONDecodeError, subprocess.CalledProcessError):
                # A corrupt or partial blob must not crash the load; skip it.
                continue
            if isinstance(task, dict):
                queue.append(task)
                loaded_shas[task_id] = sha
        self._loaded_shas = loaded_shas
        self._envelope = self._read_envelope()
        return {"queue": queue, "history": read_history(self._history_path())}

    def save(
        self, queue: list[dict[str, Any]], wrapper: dict[str, Any] | None = None
    ) -> None:
        """Persist ``queue`` as per-task refs, pruning tasks that left the queue."""
        if wrapper:
            self._envelope = {**self._envelope, **wrapper}

        seen: set[str] = set()
        for task in queue:
            task_id = task.get("id")
            if not task_id:
                # Without an id there is no ref to address; skip defensively.
                continue
            seen.add(task_id)
            new_sha = self._write_blob(_canonical_json(task))
            if self._loaded_shas.get(task_id) == new_sha:
                continue  # unchanged versus what we loaded -> nothing to write
            ref = TASKS_REF_PREFIX + task_id
            expected = self._loaded_shas.get(task_id) or _NULL_OID
            result = self._git("update-ref", ref, new_sha, expected)
            if result.returncode != 0:
                raise RuntimeError(
                    f"concurrent update detected for task {task_id}: {ref} "
                    "changed since last load"
                )
            self._loaded_shas[task_id] = new_sha

        # Prune refs for tasks that are no longer in the live queue (sealed or
        # removed). Deleting an already-absent ref is a harmless no-op.
        for ref in self._list_task_refs():
            task_id = ref[len(TASKS_REF_PREFIX) :]
            if task_id not in seen:
                self._git("update-ref", "-d", ref).check_returncode()
                self._loaded_shas.pop(task_id, None)

        # Persist the envelope with the current schema version.
        self._envelope["schema_version"] = ENVELOPE_SCHEMA_VERSION
        self._write_envelope()

    def plan_drift(self, plans_dir: str | Path) -> list[str]:
        """Return plan files that are not present in queue or history."""
        data = self.load()
        queued_files = {
            t.get("plan_file") for t in data["queue"] if t.get("plan_file")
        }
        settled_files = {
            t.get("plan_file") for t in data["history"] if t.get("plan_file")
        }
        plan_files = sorted(Path(plans_dir).glob("*.md"))
        return [
            str(pf)
            for pf in plan_files
            if str(pf) not in queued_files and str(pf) not in settled_files
        ]

    def close(self) -> None:
        """No-op: every git invocation is self-contained."""
        return

    def sync_task(self, task: dict[str, Any], is_new: bool) -> None:
        """No-op: the git-refs backend has no external task mirror."""
        return

    def seal(self, task_id: str, history_file: str) -> dict[str, Any]:
        """Drop the task's ref and append its record to the history JSONL.

        Mirrors ``queue.seal_terminal`` for the refs store: the task leaves the
        live queue (its ``refs/aet/tasks/<id>`` ref is deleted) and the full
        record — including transition history — is appended to the shared
        append-only history JSONL that both backends read. Dependents are not
        promoted here; ``aet-state`` advances the forward frontier before
        sealing.

        Like the default file-based ``seal``, this does not re-acquire the queue
        lock: ``aet-state`` already holds it, and a nested lock from the
        re-imported ``queue`` module would self-deadlock (see ``base.py``).
        Ref mutation is still atomic under git's own ref locks.
        """
        from aet.queue import append_history_record

        data = self.load()
        task = next(
            (t for t in data["queue"] if t.get("id") == task_id), None
        )
        if task is None:
            raise ValueError(
                f"Task {task_id} not found in live queue {self.queue_file}"
            )

        ref = TASKS_REF_PREFIX + task_id
        self._git("update-ref", "-d", ref).check_returncode()
        self._loaded_shas.pop(task_id, None)

        # Persist the envelope with the current schema version.
        self._envelope["schema_version"] = ENVELOPE_SCHEMA_VERSION
        self._write_envelope()

        append_history_record(self._resolve_history(history_file), task)
        return task

    # -- envelope -------------------------------------------------------------

    def _read_envelope(self) -> dict[str, Any]:
        sha = self._ref_sha(ENVELOPE_REF)
        if sha is None:
            return {}
        try:
            data = json.loads(self._read_blob(sha))
        except (json.JSONDecodeError, subprocess.CalledProcessError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_envelope(self) -> None:
        """Persist the envelope blob and point the meta ref at it.

        The envelope carries ``schema_version`` and any caller metadata; stale
        tamper-evidence keys from legacy envelopes are dropped.
        """
        self._envelope.pop("content_hash", None)
        self._envelope.pop("prev_content_hash", None)
        envelope_sha = self._write_blob(_canonical_json(self._envelope))
        if self._ref_sha(ENVELOPE_REF) != envelope_sha:
            self._git("update-ref", ENVELOPE_REF, envelope_sha).check_returncode()

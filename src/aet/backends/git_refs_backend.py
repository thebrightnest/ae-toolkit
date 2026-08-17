"""Git-refs backend for the aet-work queue.

Each live task record is stored as a JSON blob addressed by a git ref under
``refs/aet/tasks/<task-id>``. Queue envelope metadata (``source_prd``,
``queue_updated_at``, ``schema_version``, …) lives at ``refs/aet/meta/queue``.
Settled history is left in the append-only ``work-history.jsonl`` file, exactly
as the JSON backend does — this backend is storage-only; state legality stays in
``aet-state``.

Ref updates are atomic under git's own ref locks. A multi-task ``save`` writes
per-task refs and skips tasks whose blob is unchanged versus what was loaded, so
concurrent writers touching *different* tasks never clobber each other.
Replication to the forge remote is explicit: mutating ``aet-state`` commands
push ``refs/aet/*`` (forced, best-effort except at terminal closure) and read
commands fetch it back.

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
SEALED_REF_PREFIX = "refs/aet/sealed/"
ENVELOPE_REF = "refs/aet/meta/queue"
ENVELOPE_SCHEMA_VERSION = 1

# Refspecs used to fetch and push the backend's private namespace. The leading
# '+' allows refs to be overwritten in both directions, which is required
# because refs in this namespace point to blobs: git rejects any update to a
# remote ref that points at a non-commit object without force. Overwriting is
# safe because the namespace is backend-owned and tasks are identified by
# their ref names, not by a linear history.
_AET_FETCH_REFSPEC = "+refs/aet/*:refs/aet/*"
_AET_PUSH_REFSPEC = "+refs/aet/*"


def _has_remote(repo_root: str) -> bool:
    """Return True when the repository has at least one remote."""
    result = subprocess.run(
        ["git", "-C", repo_root, "remote"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())

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

    class RefsPushError(RuntimeError):
        """Raised when a mandatory push of ``refs/aet/*`` fails."""

        def __init__(self, message: str) -> None:
            super().__init__(message)

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
        # Task refs deleted by ``save()`` since the last successful ``push()``.
        # These must be pushed as deletions explicitly; a wildcard push only
        # updates refs that still exist locally.
        self._deleted_refs: set[str] = set()

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

    def _list_sealed_refs(self) -> list[str]:
        result = self._git(
            "for-each-ref", "--format=%(refname)", SEALED_REF_PREFIX
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

        Any task ref that has a corresponding ``refs/aet/sealed/<id>`` tombstone
        is treated as no longer live. The local task ref is reaped as
        housekeeping so a clone converges by reading, without requiring the
        deletion to have been delivered.
        """
        queue: list[dict[str, Any]] = []
        loaded_shas: dict[str, str] = {}
        sealed_ids = {
            ref[len(SEALED_REF_PREFIX) :]
            for ref in self._list_sealed_refs()
        }
        for ref in self._list_task_refs():
            sha = self._ref_sha(ref)
            if sha is None:
                continue
            task_id = ref[len(TASKS_REF_PREFIX) :]
            if task_id in sealed_ids:
                # Tombstone wins: reap the stale local task ref as housekeeping.
                # Failures are ignored because this is a read-path cleanup.
                self._git("update-ref", "-d", ref)
                self._loaded_shas.pop(task_id, None)
                continue
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
        """Persist ``queue`` as per-task refs, pruning tasks that left the queue.

        All ref creations, updates, deletes, and the envelope write are batched
        into a single ``git update-ref --stdin`` transaction so an interruption
        cannot leave the backend with a partial ref set (ADR-055, slc-04).
        """
        if wrapper:
            self._envelope = {**self._envelope, **wrapper}

        updates: list[tuple[str, str, str | None, str | None]] = []
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
            updates.append(("update", ref, new_sha, expected))

        # Prune refs for tasks that are no longer in the live queue (sealed or
        # removed). Use the current ref sha as the compare-and-swap value.
        for ref in self._list_task_refs():
            task_id = ref[len(TASKS_REF_PREFIX) :]
            if task_id not in seen:
                current_sha = self._ref_sha(ref)
                if current_sha is not None:
                    updates.append(("delete", ref, None, current_sha))
                    self._deleted_refs.add(ref)

        # Persist the envelope with the current schema version.
        self._envelope["schema_version"] = ENVELOPE_SCHEMA_VERSION
        self._envelope.pop("content_hash", None)
        self._envelope.pop("prev_content_hash", None)
        envelope_sha = self._write_blob(_canonical_json(self._envelope))
        current_envelope_sha = self._ref_sha(ENVELOPE_REF)
        if current_envelope_sha != envelope_sha:
            updates.append(
                ("update", ENVELOPE_REF, envelope_sha, current_envelope_sha or _NULL_OID)
            )

        if not updates:
            return

        stdin_lines: list[str] = []
        for action, ref, new_sha, old_sha in updates:
            if action == "update":
                stdin_lines.append(f"update {ref} {new_sha} {old_sha}")
            else:
                stdin_lines.append(f"delete {ref} {old_sha}")
        stdin = ("\n".join(stdin_lines) + "\n").encode("utf-8")

        result = self._git("update-ref", "--stdin", input=stdin)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"atomic ref update failed: {stderr}")

        # Commit the in-memory sha cache only after the transaction succeeds.
        for action, ref, new_sha, _old_sha in updates:
            if action == "update" and ref.startswith(TASKS_REF_PREFIX):
                task_id = ref[len(TASKS_REF_PREFIX) :]
                self._loaded_shas[task_id] = new_sha  # type: ignore[assignment]
            elif action == "delete" and ref.startswith(TASKS_REF_PREFIX):
                task_id = ref[len(TASKS_REF_PREFIX) :]
                self._loaded_shas.pop(task_id, None)

    def close(self) -> None:
        """No-op: every git invocation is self-contained."""
        return

    def fetch(self) -> None:
        """Fetch ``refs/aet/*`` from ``origin``.

        Best-effort: a missing remote or transient network failure is ignored,
        because read-only commands should not fail when offline. The fetched
        refs overwrite local ones in the backend namespace.
        """
        if not _has_remote(self.repo_root):
            return
        self._git("fetch", "origin", _AET_FETCH_REFSPEC)

    def push(self, *, mandatory: bool = False) -> bool:
        """Push ``refs/aet/*`` to ``origin``.

        Best-effort by default: returns ``False`` on failure without raising so
        local operation is never blocked. When ``mandatory`` is ``True`` (terminal
        closure boundary), a failure raises :exc:`RefsPushError` naming the
        recovery action.

        A repository with no remote is treated as success for best-effort pushes
        (there is nothing to push), but mandatory pushes raise because the
        durability guarantee cannot be satisfied without a remote.
        """
        if not _has_remote(self.repo_root):
            if mandatory:
                raise self.RefsPushError(
                    "No remote configured; cannot satisfy mandatory push of refs/aet/*.\n"
                    "Add an origin remote and re-run `aet ship close` to retry the push."
                )
            return True

        result = self._git("push", "origin", _AET_PUSH_REFSPEC)
        if result.returncode != 0:
            if mandatory:
                stderr = result.stderr.decode("utf-8", errors="replace").strip()
                raise self.RefsPushError(
                    f"Mandatory push of refs/aet/* failed: {stderr}\n"
                    "Local closure is intact. Re-run `aet ship close` to retry the push."
                )
            return False

        # Push explicit deletions for refs pruned since the last push. A
        # wildcard push only updates refs that still exist locally, so sealed
        # task refs would otherwise remain on the remote indefinitely.
        if self._deleted_refs:
            delete_refspecs = [f":{ref}" for ref in sorted(self._deleted_refs)]
            del_result = self._git(
                "push", "origin", _AET_PUSH_REFSPEC, *delete_refspecs
            )
            if del_result.returncode == 0:
                self._deleted_refs.clear()
            elif mandatory:
                stderr = del_result.stderr.decode("utf-8", errors="replace").strip()
                raise self.RefsPushError(
                    f"Mandatory push of deleted refs/aet/* failed: {stderr}\n"
                    "Local closure is intact. Re-run `aet ship close` to retry the push."
                )
            else:
                return False

        return True

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

        A per-task tombstone ref ``refs/aet/sealed/<id>`` is written in the
        same atomic transaction as the task ref deletion so the two cannot
        diverge. The tombstone replicates by fetch/push and lets other clones
        converge by reading, without depending on the deletion being delivered
        (ADR-055).

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

        task_ref = TASKS_REF_PREFIX + task_id
        sealed_ref = SEALED_REF_PREFIX + task_id
        tombstone_sha = self._write_blob(_canonical_json(task))
        current_task_sha = self._ref_sha(task_ref) or _NULL_OID
        current_sealed_sha = self._ref_sha(sealed_ref) or _NULL_OID

        stdin = (
            f"delete {task_ref} {current_task_sha}\n"
            f"update {sealed_ref} {tombstone_sha} {current_sealed_sha}\n"
        ).encode("utf-8")
        result = self._git("update-ref", "--stdin", input=stdin)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"atomic seal update failed: {stderr}")

        self._loaded_shas.pop(task_id, None)
        self._deleted_refs.add(task_ref)

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

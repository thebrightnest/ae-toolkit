"""Single-run file-hash cache for stage-scoped validation.

``aet-implement`` uses :class:`ValidationCache` to avoid re-running targeted
validations when source, test, and dependency files have not changed within the
current orchestration run. The cache is intentionally run-scoped and is never
reused across runs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Paths that, when changed, can affect validation outcomes.
_TRACKED_ROOT_FILES: frozenset[str] = frozenset(
    {
        "pyproject.toml",
    }
)

# Lockfiles that pin the dependency surface. Only files that exist are hashed.
_LOCKFILE_NAMES: frozenset[str] = frozenset(
    {
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "requirements.lock",
    }
)

# Directories whose contents are hashed for cache invalidation.
_TRACKED_DIRS: tuple[str, ...] = ("src", "tests")

# Build artifacts that should not affect the file-hash snapshot.
_IGNORED_DIR_NAMES: frozenset[str] = frozenset({"__pycache__"})
_IGNORED_FILE_SUFFIXES: tuple[str, ...] = (".pyc",)


def _hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of ``path``'s contents."""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _hash_text(text: str) -> str:
    """Return the SHA-256 hex digest of ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ValidationCache:
    """File-hash validation cache scoped to a single orchestration run.

    The cache lives on disk at ``cache_path`` and is read/written as JSON.
    Entries are keyed by validation command and by a file-hash snapshot of the
    repository. Cross-run reuse is prevented by giving each run its own cache
    file.
    """

    def __init__(self, repo_root: str | Path, cache_path: str | Path | None = None):
        self.repo_root = Path(repo_root).resolve()
        self.cache_path = (
            Path(cache_path).resolve()
            if cache_path is not None
            else self.repo_root / ".agents" / "runs" / "default" / "validation-cache.json"
        )

    @classmethod
    def for_run(cls, repo_root: str | Path, run_id: str) -> "ValidationCache":
        """Return a cache backed by the run-scoped path for ``run_id``."""
        cache_path = Path(repo_root).resolve() / ".agents" / "runs" / run_id / "validation-cache.json"
        return cls(repo_root, cache_path)

    def compute_hash(self) -> str:
        """Compute a SHA-256 hash snapshot of tracked source/test/dependency files.

        The digest is deterministic: files are walked in sorted order and the
        final hash combines relative paths with their individual content hashes.
        Bytecode artifacts (``__pycache__`` and ``.pyc`` files) are ignored so
        test runs do not spuriously invalidate the cache.
        """
        pieces: list[str] = []

        for rel_dir in _TRACKED_DIRS:
            dir_path = self.repo_root / rel_dir
            if not dir_path.exists():
                continue
            for path in sorted(dir_path.rglob("*")):
                if not path.is_file():
                    continue
                rel_parts = path.relative_to(self.repo_root).parts
                if any(part in _IGNORED_DIR_NAMES for part in rel_parts):
                    continue
                if path.suffix in _IGNORED_FILE_SUFFIXES:
                    continue
                rel = path.relative_to(self.repo_root).as_posix()
                pieces.append(f"{rel}:{_hash_file(path)}")

        for rel_file in sorted(_TRACKED_ROOT_FILES):
            path = self.repo_root / rel_file
            if path.is_file():
                pieces.append(f"{rel_file}:{_hash_file(path)}")

        for rel_file in sorted(_LOCKFILE_NAMES):
            path = self.repo_root / rel_file
            if path.is_file():
                pieces.append(f"{rel_file}:{_hash_file(path)}")

        return _hash_text("\n".join(pieces))

    def _load(self) -> dict[str, dict[str, dict[str, object]]]:
        """Load the cache from disk, returning an empty dict on any error."""
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if isinstance(data, dict):
            return data
        return {}

    def _save(self, data: dict[str, dict[str, dict[str, object]]]) -> None:
        """Persist the cache to disk atomically."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def get(self, command: str, file_hash: str) -> dict[str, object] | None:
        """Return the cached result for ``command`` and ``file_hash``, or None."""
        data = self._load()
        return data.get(command, {}).get(file_hash)

    def set(
        self,
        command: str,
        file_hash: str,
        result: dict[str, object],
    ) -> None:
        """Store ``result`` for ``command`` under ``file_hash``."""
        data = self._load()
        data.setdefault(command, {})[file_hash] = result
        self._save(data)

    def is_cached(self, command: str, file_hash: str) -> bool:
        """Return True when a result exists for ``command`` + ``file_hash``."""
        return self.get(command, file_hash) is not None

"""Backend factory for aet-work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backends.base import TaskBackend
from backends.git_refs_backend import GitRefsBackend
from backends.github_backend import GitHubBackend
from backends.json_backend import JsonBackend

DEFAULT_CONFIG_PATH = ".agents/aet-work.json"


def create_backend(
    config_path: str | None = None,
    queue_file: str = ".agents/work-queue.json",
    history_file: str = ".agents/work-history.jsonl",
) -> TaskBackend:
    """Instantiate a task backend based on ``.agents/aet-work.json``.

    The configuration key ``task_backend`` selects the implementation:
    ``json``, ``git-refs``, ``github``, or ``both``. aet-setup writes
    ``git-refs`` by default (``aet configure-backend``); ``json`` is the
    documented opt-out and remains the fallback here for unconfigured or
    non-git contexts.
    """
    config_path = config_path or DEFAULT_CONFIG_PATH
    config = _read_config(config_path)
    backend_type = config.get("task_backend", "json")

    if backend_type == "json":
        return JsonBackend(queue_file=queue_file, history_file=history_file)
    if backend_type == "git-refs":
        return GitRefsBackend(queue_file=queue_file, history_file=history_file)
    if backend_type == "github":
        github_config = config.get("github", {})
        repo = github_config.get("repo", "")
        if not repo:
            raise ValueError("GitHub backend requires config.github.repo")
        return GitHubBackend(
            queue_file=queue_file,
            history_file=history_file,
            repo=repo,
            label_prefix=github_config.get("label_prefix", "aet"),
        )
    if backend_type == "both":
        raise NotImplementedError("Composite backend is not yet implemented")

    raise ValueError(f"Unknown task_backend: {backend_type}")


def _read_config(config_path: str) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        return {"task_backend": "json"}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

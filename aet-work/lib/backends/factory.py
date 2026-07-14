"""Backend factory for aet-work."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backends.base import TaskBackend
from backends.git_refs_backend import GitRefsBackend
from backends.github_backend import GitHubBackend
from backends.json_backend import JsonBackend
from project_id import derive_project_slug

DEFAULT_CONFIG_PATH = ".agents/aet-work.json"

# Environment variable that overrides the config file location. Highest
# precedence in the external-first resolution order.
AET_WORK_CONFIG_ENV = "AET_WORK_CONFIG"


def create_backend(
    config_path: str | None = None,
    queue_file: str = ".agents/work-queue.json",
    history_file: str = ".agents/work-history.jsonl",
) -> TaskBackend:
    """Instantiate a task backend based on the resolved AET config.

    Configuration is resolved with external-first precedence:
    ``AET_WORK_CONFIG`` env → ``~/.aet/{slug}/config.json`` → in-tree
    ``.agents/aet-work.json`` → built-in defaults. The ``task_backend`` key
    selects the implementation: ``json``, ``git-refs``, ``github``, or
    ``both``. aet-setup writes ``git-refs`` by default; ``json`` is the
    documented opt-out and remains the fallback for unconfigured contexts.
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


def _load_config(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_config(config_path: str) -> dict[str, Any]:
    """Resolve config with external-first precedence.

    Order: env ``AET_WORK_CONFIG`` → external ``~/.aet/{slug}/config.json``
    → in-tree ``config_path`` → built-in defaults.
    """
    env_override = os.environ.get(AET_WORK_CONFIG_ENV)
    if env_override:
        path = Path(env_override)
        if path.exists():
            return _load_config(path)

    slug = derive_project_slug()
    external_path = Path.home() / ".aet" / slug / "config.json"
    if external_path.exists():
        return _load_config(external_path)

    path = Path(config_path)
    if path.exists():
        return _load_config(path)

    return {"task_backend": "json"}

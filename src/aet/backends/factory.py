"""Backend factory for aet-work."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aet.backends.git_refs_backend import GitRefsBackend
from aet.backends.json_backend import JsonBackend
from aet.project_id import derive_project_slug

DEFAULT_CONFIG_PATH = ".agents/aet-work.json"

# Environment variable that overrides the config file location. Highest
# precedence in the external-first resolution order.
AET_WORK_CONFIG_ENV = "AET_WORK_CONFIG"


class UnknownBackendError(ValueError):
    """Raised when ``task_backend`` selects a value with no storage implementation.

    ``github`` and ``both`` are no longer valid storage selections; use the
    ``projections`` config axis instead.
    """


def create_backend(
    config_path: str | None = None,
    queue_file: str = ".agents/work-queue.json",
    history_file: str = ".agents/work-history.jsonl",
) -> JsonBackend | GitRefsBackend:
    """Instantiate a task backend based on the resolved AET config.

    Configuration is resolved with external-first precedence:
    ``AET_WORK_CONFIG`` env → ``~/.aet/{slug}/config.json`` → in-tree
    ``.agents/aet-work.json`` → built-in defaults. The ``task_backend`` key
    selects the implementation: ``json`` or ``git-refs``. Forge values such as
    ``github`` or ``both`` are rejected with :class:`UnknownBackendError` and
    must be configured on the orthogonal ``projections`` axis.
    """
    config = resolve_config(config_path or DEFAULT_CONFIG_PATH)
    backend_type = config.get("task_backend", "json")

    if backend_type == "json":
        return JsonBackend(queue_file=queue_file, history_file=history_file)
    if backend_type == "git-refs":
        return GitRefsBackend(queue_file=queue_file, history_file=history_file)

    raise UnknownBackendError(
        f"Unknown task_backend: {backend_type!r}. "
        "Choose 'json' or 'git-refs'. "
        "For GitHub Issues mirroring, use the 'projections' config axis."
    )


def resolve_config(config_path: str) -> dict[str, Any]:
    """Resolve AET config with external-first precedence.

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

    return {"task_backend": "json", "trunk_branch": None, "integration_branch": None}


def _load_config(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

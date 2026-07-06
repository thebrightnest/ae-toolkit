"""Backend factory for aet-work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backends.base import TaskBackend
from backends.json_backend import JsonBackend

DEFAULT_CONFIG_PATH = ".agents/aet-work.json"


def create_backend(
    config_path: str | None = None,
    queue_file: str = ".agents/work-queue.json",
    history_file: str = ".agents/work-history.jsonl",
) -> TaskBackend:
    """Instantiate a task backend based on ``.agents/aet-work.json``.

    The configuration key ``task_backend`` selects the implementation:
    ``json`` (default), ``github``, or ``both``. Unsupported or missing values
    fall back to the JSON backend for local-only operation.
    """
    config_path = config_path or DEFAULT_CONFIG_PATH
    backend_type = _read_backend_type(config_path)

    if backend_type == "json":
        return JsonBackend(queue_file=queue_file, history_file=history_file)
    if backend_type == "github":
        raise NotImplementedError("GitHub backend is not yet implemented")
    if backend_type == "both":
        raise NotImplementedError("Composite backend is not yet implemented")

    raise ValueError(f"Unknown task_backend: {backend_type}")


def _read_backend_type(config_path: str) -> str:
    path = Path(config_path)
    if not path.exists():
        return "json"

    with open(path, "r", encoding="utf-8") as f:
        config: dict[str, Any] = json.load(f)

    return config.get("task_backend", "json")

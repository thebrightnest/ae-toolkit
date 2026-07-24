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


class IntegrationModeError(ValueError):
    """Raised when ``integration_mode`` has an unrecognized value."""


# Legal values for the ``integration_mode`` project setting.
INTEGRATION_MODES = frozenset({"pr-per-task", "single-pr"})


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


def resolve_config_with_source(config_path: str) -> tuple[dict[str, Any], str]:
    """Resolve AET config and report which layer supplied it.

    Order: env ``AET_WORK_CONFIG`` → external ``~/.aet/{slug}/config.json``
    → in-tree ``config_path`` → built-in defaults. Returns ``(config, source)``
    where ``source`` is one of ``env``, ``user``, ``project``, or ``default``.
    """
    env_override = os.environ.get(AET_WORK_CONFIG_ENV)
    if env_override:
        path = Path(env_override)
        if path.exists():
            return _load_config(path), "env"

    slug = derive_project_slug()
    external_path = Path.home() / ".aet" / slug / "config.json"
    if external_path.exists():
        return _load_config(external_path), "user"

    path = Path(config_path)
    if path.exists():
        return _load_config(path), "project"

    defaults = {"task_backend": "json", "trunk_branch": None, "integration_branch": None}
    return defaults, "default"


def resolve_config(config_path: str) -> dict[str, Any]:
    """Resolve AET config with external-first precedence.

    Order: env ``AET_WORK_CONFIG`` → external ``~/.aet/{slug}/config.json``
    → in-tree ``config_path`` → built-in defaults.
    """
    return resolve_config_with_source(config_path)[0]


def resolve_integration_mode(config_path: str | None = None) -> str:
    """Resolve ``integration_mode`` through the external-first config chain.

    Uses the same precedence as :func:`resolve_config`: env ``AET_WORK_CONFIG``
    → external ``~/.aet/{slug}/config.json`` → in-tree ``config_path`` →
    built-in default. The default is ``pr-per-task``. An unrecognized value
    fails closed with a message naming the key and the legal values.
    """
    config = resolve_config(config_path or DEFAULT_CONFIG_PATH)
    mode = config.get("integration_mode", "pr-per-task")
    if mode in INTEGRATION_MODES:
        return mode
    raise IntegrationModeError(
        f"Invalid integration_mode: {mode!r}. "
        f"Choose one of: {', '.join(sorted(INTEGRATION_MODES))}."
    )


def resolve_integration_mode_with_provenance(
    config_path: str | None = None,
) -> tuple[str, str]:
    """Resolve ``integration_mode`` and report where the value came from.

    Returns ``(mode, provenance)`` where provenance is ``config (project)``,
    ``config (user)``, ``config (env)``, or ``default``.
    """
    config, source = resolve_config_with_source(config_path or DEFAULT_CONFIG_PATH)
    if "integration_mode" in config:
        return config["integration_mode"], f"config ({source})"
    return "pr-per-task", "default"


def _load_config(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

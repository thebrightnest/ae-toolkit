"""Backend factory for aet-work."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aet.backends.git_refs_backend import GitRefsBackend
from aet.backends.json_backend import JsonBackend
from aet.project_id import derive_config_slug, resolve_repo_root

DEFAULT_CONFIG_PATH = ".agents/aet-config.json"
LEGACY_CONFIG_PATH = ".agents/aet-work.json"

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


class LegacyConfigError(ValueError):
    """Raised when only the legacy in-tree config file exists.

    The canonical in-tree file is ``.agents/aet-config.json``. If the legacy
    ``.agents/aet-work.json`` is present and the new file is not, callers must
    run ``aet configure --migrate`` before AET can read the config.
    """


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
    ``.agents/aet-config.json`` → built-in defaults. The ``task_backend`` key
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


def resolve_config_with_source(
    config_path: str, repo_root: str | Path | None = None
) -> tuple[dict[str, Any], str]:
    """Resolve AET config and report which layer supplied it.

    Order: env ``AET_WORK_CONFIG`` → external ``~/.aet/{slug}/config.json``
    → in-tree ``config_path`` → built-in defaults. Returns ``(config, source)``
    where ``source`` is one of ``env``, ``user``, ``project``, or ``default``.

    The in-tree path is anchored to the repository root, not the process cwd,
    so subdirectory invocations resolve the same config as root invocations.
    When ``repo_root`` is provided it is used directly; otherwise the root is
    discovered via ``resolve_repo_root()``.

    If the legacy ``.agents/aet-work.json`` exists and the canonical
    ``.agents/aet-config.json`` does not, resolution fails closed with
    :class:`LegacyConfigError` naming ``aet configure --migrate`` as the
    remedy.
    """
    env_override = os.environ.get(AET_WORK_CONFIG_ENV)
    if env_override:
        path = Path(env_override)
        if path.exists():
            return _load_config(path), "env"

    slug = derive_config_slug(repo_root)
    external_path = Path.home() / ".aet" / slug / "config.json"
    if external_path.exists():
        return _load_config(external_path), "user"

    root = resolve_repo_root(repo_root)
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path

    if path.exists():
        return _load_config(path), "project"

    legacy_path = root / LEGACY_CONFIG_PATH
    if legacy_path.exists():
        raise LegacyConfigError(
            f"Legacy config found at {LEGACY_CONFIG_PATH}. "
            "Run `aet configure --migrate` to rename it to "
            f"{DEFAULT_CONFIG_PATH}."
        )

    defaults = {"task_backend": "json", "trunk_branch": None, "integration_branch": None}
    return defaults, "default"


def resolve_config(
    config_path: str, repo_root: str | Path | None = None
) -> dict[str, Any]:
    """Resolve AET config with external-first precedence.

    Order: env ``AET_WORK_CONFIG`` → external ``~/.aet/{slug}/config.json``
    → in-tree ``config_path`` → built-in defaults.

    The in-tree path is anchored to the repository root, not the process cwd,
    so subdirectory invocations resolve the same config as root invocations.
    When ``repo_root`` is provided it is used directly; otherwise the root is
    discovered via ``resolve_repo_root()``.

    If the legacy ``.agents/aet-work.json`` exists and the canonical
    ``.agents/aet-config.json`` does not, resolution fails closed with
    :class:`LegacyConfigError` naming ``aet configure --migrate`` as the
    remedy.
    """
    return resolve_config_with_source(config_path, repo_root=repo_root)[0]


def resolve_integration_mode(
    config_path: str | None = None, repo_root: str | Path | None = None
) -> str:
    """Resolve ``integration_mode`` through the external-first config chain.

    Uses the same precedence as :func:`resolve_config`: env ``AET_WORK_CONFIG``
    → external ``~/.aet/{slug}/config.json`` → in-tree ``config_path`` →
    built-in default. The in-tree path is anchored to the repository root.
    The default is ``pr-per-task``. An unrecognized value fails closed with a
    message naming the key and the legal values.
    """
    config = resolve_config(config_path or DEFAULT_CONFIG_PATH, repo_root=repo_root)
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

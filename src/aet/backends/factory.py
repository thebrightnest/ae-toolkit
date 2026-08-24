"""Backend factory for aet-work."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aet.backends.base import SHADOW_POSTURE, SHARED_POSTURE
from aet.backends.git_refs_backend import GitRefsBackend
from aet.project_id import derive_config_slug, resolve_repo_root

DEFAULT_CONFIG_PATH = ".agents/aet-config.json"
LEGACY_CONFIG_PATH = ".agents/aet-work.json"

# Environment variable that overrides the config file location. Highest
# precedence in the external-first resolution order.
AET_WORK_CONFIG_ENV = "AET_WORK_CONFIG"


class LegacyTaskBackendError(ValueError):
    """Raised when a config still carries the removed ``task_backend`` key.

    git-refs is the only task store; the ``task_backend`` selection axis was
    removed. Configs that still set it must drop the key.
    """


class IntegrationModeError(ValueError):
    """Raised when ``integration_mode`` has an unrecognized value."""


class QueueOutsideRepositoryError(RuntimeError):
    """Raised when the queue path is not inside a git repository.

    git-refs keeps state in ``refs/aet/*`` inside the repository that holds
    the queue. When the queue path is not inside a git work tree there is no
    such repository, so the selection is refused by name rather than surfacing
    as a traceback from the backend's own discovery.
    """


class LegacyConfigError(ValueError):
    """Raised when only the legacy in-tree config file exists.

    The canonical in-tree file is ``.agents/aet-config.json``. If the legacy
    ``.agents/aet-work.json`` is present and the new file is not, callers must
    run ``aet configure --migrate`` before AET can read the config.
    """


class UnknownConfigKeyError(ValueError):
    """Raised when a config file contains a key that is not legal."""


class ConfigContradictionError(ValueError):
    """Raised when config contains mutually exclusive settings."""


# Legal values for the ``integration_mode`` project setting.
INTEGRATION_MODES = frozenset({"pr-per-task", "single-pr"})

# Legal top-level keys for an AET config file. Removed keys (e.g. task_backend)
# are special-cased with a migration message before this set is consulted.
LEGAL_CONFIG_KEYS = frozenset({
    "trunk_branch",
    "integration_branch",
    "integration_mode",
    "projections",
    "github",  # legacy top-level fallback read by resolve_projections
    "boundary_contract",  # read by aet.boundary
    "symlink_dependencies",  # read by aet.worktree
})

# Removed-key migration message reused by config resolution and CLI.
_TASK_BACKEND_REMOVED_MSG = (
    "Migration: the 'task_backend' config key has been removed. "
    "git-refs is the only task store. "
    "Remove 'task_backend' from your AET config and re-run the command."
)


def queue_repo_root(queue_file: str) -> str | None:
    """Return the git work-tree root containing ``queue_file``, or ``None``.

    Discovery starts at the queue file's own location rather than the process
    cwd, so the store and the configuration that selects it are anchored to one
    repository. The queue file's directory need not exist yet, so discovery
    walks up to the nearest existing ancestor first — which is also what keeps a
    subdirectory invocation resolving the repository root.

    The walk tests for a ``.git`` entry rather than shelling out to ``git
    rev-parse``: config resolution runs on every command, including the
    status/next read path, which must invoke no git subprocess
    (``tests/orchestrator/test_read_path_no_git.py``). A ``.git`` *file* rather
    than a directory is a linked worktree, whose work-tree root is where that
    file lives — the same answer ``--show-toplevel`` gives.
    """
    directory = Path(queue_file).resolve().parent
    while not directory.is_dir() and directory != directory.parent:
        directory = directory.parent
    for candidate in [directory, *directory.parents]:
        if (candidate / ".git").exists():
            return str(candidate)
    return None


def create_backend(
    config_path: str | None = None,
    queue_file: str = ".agents/aet-queue",
    history_file: str = ".agents/work-history.jsonl",
) -> GitRefsBackend:
    """Instantiate the git-refs task backend.

    Configuration is resolved with external-first precedence:
    ``AET_WORK_CONFIG`` env → ``~/.aet/{slug}/config.json`` → in-tree
    ``.agents/aet-config.json`` → built-in defaults. A surviving
    ``task_backend`` key fails closed with a migration message.

    The backend's ``posture`` attribute is ``shared`` when project-scope config
    exists and ``shadow`` otherwise. Shadow posture suppresses all pushes and
    projections and keeps AET artifacts out of the working tree.
    """
    queue_root = queue_repo_root(queue_file)
    # Anchor configuration to the repository that holds the queue, not to the
    # process cwd. Both must agree: selecting a backend from repository A and
    # rooting its store in repository B is how a project config in one tree
    # silently governed operations on a queue in another.
    # Resolve config to fail fast on removed keys; git-refs is the only store,
    # so the resolved dict is no longer consulted.
    config, source = resolve_config_with_source(
        config_path or DEFAULT_CONFIG_PATH,
        repo_root=queue_root or str(Path(queue_file).resolve().parent),
    )
    if queue_root is None:
        raise QueueOutsideRepositoryError(
            "git-refs stores state in refs/aet/* inside the repository holding "
            f"the queue, but {queue_file} is not inside a git repository."
        )
    posture = SHARED_POSTURE if source == "project" else SHADOW_POSTURE
    return GitRefsBackend(
        queue_file=queue_file,
        history_file=history_file,
        repo_root=queue_root,
        posture=posture,
    )


def resolve_posture(
    config_path: str, repo_root: str | Path | None = None
) -> str:
    """Infer project posture from the config source.

    Returns ``shared`` when an in-tree project-scope config is the effective
    source, and ``shadow`` for any other source (env, user, or default). A
    project nobody configured is therefore local by default.
    """
    _, source = resolve_config_with_source(config_path, repo_root=repo_root)
    return SHARED_POSTURE if source == "project" else SHADOW_POSTURE


def _validate_config_keys(config: dict[str, Any]) -> None:
    """Reject unknown keys, naming the legal ones."""
    unknown = set(config.keys()) - LEGAL_CONFIG_KEYS
    if unknown:
        raise UnknownConfigKeyError(
            f"Unknown config key(s): {', '.join(sorted(unknown))}. "
            f"Legal keys are: {', '.join(sorted(LEGAL_CONFIG_KEYS))}."
        )


def _validate_config_consistency(
    config: dict[str, Any], source: str, project_path: Path | None
) -> None:
    """Reject combinations that cannot take effect in the resolved posture.

    Projections are a shared-device feature: they write to a forge and assume
    refs/aet/* are pushed. In shadow posture (any source other than project)
    a ``projections`` entry is a contradiction.
    """
    if source != "project" and "projections" in config:
        raise ConfigContradictionError(
            "Config source is shadow (no project-scope config is effective), "
            "but a 'projections' entry is present. Projections require shared "
            "posture and must live in the in-tree team config. "
            f"Move 'projections' to {project_path or '.agents/aet-config.json'} "
            "or remove it."
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

    Unknown keys fail closed, naming the legal alternatives. A surviving
    ``task_backend`` key fails closed with a migration message. A
    ``projections`` entry in a shadow source fails closed because projections
    require shared posture.

    If the legacy ``.agents/aet-work.json`` exists and the canonical
    ``.agents/aet-config.json`` does not, resolution fails closed with
    :class:`LegacyConfigError` naming ``aet configure --migrate`` as the
    remedy.
    """
    root = resolve_repo_root(repo_root)
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path

    env_override = os.environ.get(AET_WORK_CONFIG_ENV)
    if env_override:
        env_path = Path(env_override)
        if env_path.exists():
            config = _load_config(env_path)
            if "task_backend" in config:
                raise LegacyTaskBackendError(_TASK_BACKEND_REMOVED_MSG)
            _validate_config_keys(config)
            _validate_config_consistency(config, "env", project_path=path)
            return config, "env"

    slug = derive_config_slug(repo_root)
    external_path = Path.home() / ".aet" / slug / "config.json"
    if external_path.exists():
        config = _load_config(external_path)
        if "task_backend" in config:
            raise LegacyTaskBackendError(_TASK_BACKEND_REMOVED_MSG)
        _validate_config_keys(config)
        _validate_config_consistency(config, "user", project_path=path)
        return config, "user"

    if path.exists():
        config = _load_config(path)
        if "task_backend" in config:
            raise LegacyTaskBackendError(_TASK_BACKEND_REMOVED_MSG)
        _validate_config_keys(config)
        _validate_config_consistency(config, "project", project_path=path)
        return config, "project"

    legacy_path = root / LEGACY_CONFIG_PATH
    if legacy_path.exists():
        raise LegacyConfigError(
            f"Legacy config found at {LEGACY_CONFIG_PATH}. "
            "Run `aet configure --migrate` to rename it to "
            f"{DEFAULT_CONFIG_PATH}."
        )

    defaults = {"trunk_branch": None, "integration_branch": None}
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

    A surviving ``task_backend`` key fails closed with
    :class:`LegacyTaskBackendError` naming the migration action.
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

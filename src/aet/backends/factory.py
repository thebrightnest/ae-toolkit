"""Backend factory for aet-work."""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any

from aet import user_paths
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


class MissingModelConfigError(ValueError):
    """Raised when ``models.fast`` or ``models.frontier`` is not configured."""


# Legal values for the ``integration_mode`` project setting.
INTEGRATION_MODES = frozenset({"pr-per-task", "single-pr"})

# Personal AI provider/model keys (allowed in ~/.aet/config.json and ~/.aet/{slug}/config.json,
# forbidden in committed .agents/aet-config.json).
AI_CONFIG_KEYS = frozenset({"provider", "models"})
LEGAL_MODEL_TIER_KEYS = frozenset({"fast", "frontier"})

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
    "release_prep",  # read by aet.cli.release_prep
    "validate_command",
    "lint_command",
    "validation_timeout",
    "provider",
    "models",
})

DEFAULT_VALIDATION_TIMEOUT: int = 600

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

    AI provider and model configuration is personal user state and must never
    be committed into the in-tree project config (``.agents/aet-config.json``).
    """
    if source != "project" and "projections" in config:
        raise ConfigContradictionError(
            "Config source is shadow (no project-scope config is effective), "
            "but a 'projections' entry is present. Projections require shared "
            "posture and must live in the in-tree team config. "
            f"Move 'projections' to {project_path or '.agents/aet-config.json'} "
            "or remove it."
        )
    if source == "project" and (AI_CONFIG_KEYS & set(config.keys())):
        present = ", ".join(sorted(AI_CONFIG_KEYS & set(config.keys())))
        raise ConfigContradictionError(
            f"AI configuration key(s) ({present}) are personal settings and must "
            f"not live in the committed project config ({project_path or '.agents/aet-config.json'}). "
            "Configure them globally in ~/.aet/config.json with: "
            "aet configure --global --fast-model <model> --frontier-model <model>"
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
    external_path = user_paths.user_config_path(slug)
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


DEFAULT_VALIDATE_COMMAND = ["make", "validate"]


def resolve_validation_commands(
    repo_root: str | Path | None = None,
    config_path: str | None = None,
) -> tuple[list[str], list[str] | None]:
    """Resolve validation commands from AET config.

    Returns ``(validate_cmd, lint_cmd)`` where ``validate_cmd`` defaults to
    ``["make", "validate"]`` and ``lint_cmd`` defaults to ``None``.
    String values in config are split using :func:`shlex.split`.
    """
    config = resolve_config(config_path or DEFAULT_CONFIG_PATH, repo_root=repo_root)
    validate_raw = config.get("validate_command")
    if validate_raw is not None:
        if isinstance(validate_raw, str):
            validate_cmd = shlex.split(validate_raw)
        elif isinstance(validate_raw, list):
            validate_cmd = list(validate_raw)
        else:
            validate_cmd = shlex.split(str(validate_raw))
    else:
        validate_cmd = list(DEFAULT_VALIDATE_COMMAND)

    lint_raw = config.get("lint_command")
    if lint_raw is not None:
        if isinstance(lint_raw, str):
            lint_cmd = shlex.split(lint_raw)
        elif isinstance(lint_raw, list):
            lint_cmd = list(lint_raw)
        else:
            lint_cmd = shlex.split(str(lint_raw))
    else:
        lint_cmd = None

    return validate_cmd, lint_cmd


def resolve_validation_timeout(
    repo_root: str | Path | None = None,
    config_path: str | None = None,
) -> int:
    """Resolve validation timeout in seconds from AET config.

    Precedence: AET_VALIDATION_TIMEOUT env var -> config file -> 600s default.
    """
    env_val = os.environ.get("AET_VALIDATION_TIMEOUT")
    if env_val:
        try:
            return int(env_val)
        except (ValueError, TypeError):
            pass
    config = resolve_config(config_path or DEFAULT_CONFIG_PATH, repo_root=repo_root)
    raw_val = config.get("validation_timeout")
    if raw_val is not None:
        try:
            return int(raw_val)
        except (ValueError, TypeError):
            return DEFAULT_VALIDATION_TIMEOUT
    return DEFAULT_VALIDATION_TIMEOUT


def resolve_ai_config(
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve personal AI provider and model configuration.

    Order:
    1. ``~/.aet/config.json`` (global user config, or ``AET_GLOBAL_CONFIG``)
    2. ``~/.aet/{slug}/config.json`` (per-project user shadow override, if present)
    3. ``AET_WORK_CONFIG`` env override (if present)

    Returns ``{"provider": str | None, "models": {"fast": str | None, "frontier": str | None}}``.
    """
    provider: str | None = None
    provider_source: str | None = None
    models: dict[str, str | None] = {"fast": None, "frontier": None}
    models_source: dict[str, str] = {}

    def _merge_layer(raw: dict[str, Any], source_label: str) -> None:
        nonlocal provider, provider_source
        if "provider" in raw and raw["provider"] is not None:
            if not isinstance(raw["provider"], str) or not raw["provider"].strip():
                raise ValueError("Config key 'provider' must be a non-empty string.")
            provider = raw["provider"].strip()
            provider_source = source_label
        if "models" in raw and raw["models"] is not None:
            raw_models = raw["models"]
            if not isinstance(raw_models, dict):
                raise ValueError("Config key 'models' must be a JSON object with 'fast' and 'frontier'.")
            unknown_tiers = set(raw_models.keys()) - LEGAL_MODEL_TIER_KEYS
            if unknown_tiers:
                raise UnknownConfigKeyError(
                    f"Unknown model tier(s): {', '.join(sorted(unknown_tiers))}. "
                    f"Legal model tiers are: {', '.join(sorted(LEGAL_MODEL_TIER_KEYS))}."
                )
            for tier in LEGAL_MODEL_TIER_KEYS:
                val = raw_models.get(tier)
                if val is not None:
                    if not isinstance(val, str) or not val.strip():
                        raise ValueError(f"Config key 'models.{tier}' must be a non-empty string.")
                    models[tier] = val.strip()
                    models_source[tier] = source_label

    global_path = user_paths.global_config_path()
    if global_path.exists():
        global_cfg = _load_config(global_path)
        _validate_config_keys(global_cfg)
        _merge_layer(global_cfg, "config (global)")

    try:
        slug = derive_config_slug(repo_root)
        user_path = user_paths.user_config_path(slug)
        if user_path.exists() and user_path.resolve() != global_path.resolve():
            user_cfg = _load_config(user_path)
            _validate_config_keys(user_cfg)
            _merge_layer(user_cfg, "config (user)")
    except Exception as exc:
        if isinstance(exc, (UnknownConfigKeyError, ValueError)):
            raise

    env_override = os.environ.get(AET_WORK_CONFIG_ENV)
    if env_override:
        env_path = Path(env_override)
        if env_path.exists():
            env_cfg = _load_config(env_path)
            _validate_config_keys(env_cfg)
            _merge_layer(env_cfg, "config (env)")

    return {
        "provider": provider,
        "provider_source": provider_source,
        "models": models,
        "models_source": models_source,
    }


def require_models_configured(
    repo_root: str | Path | None = None,
) -> dict[str, str]:
    """Validate that both ``models.fast`` and ``models.frontier`` are configured.

    Returns ``{"fast": str, "frontier": str}`` when valid, or raises
    :class:`MissingModelConfigError` with actionable remediation instructions.
    """
    ai_cfg = resolve_ai_config(repo_root=repo_root)
    models = ai_cfg.get("models") or {}
    missing = [tier for tier in ("fast", "frontier") if not models.get(tier)]
    if missing:
        missing_str = ", ".join(f"models.{t}" for t in missing)
        global_path = user_paths.global_config_path()
        raise MissingModelConfigError(
            f"AI models are not configured ({missing_str} missing in {global_path}).\n"
            "   Configure your global models once with:\n"
            "     aet configure --global --fast-model <model> --frontier-model <model>"
        )
    return {"fast": str(models["fast"]), "frontier": str(models["frontier"])}


def _load_config(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

"""The shared test-runner registry.

One registry owns the runner set: both ``wirelog.is_test_command`` (detection)
and ``telemetry.classify_test_scope`` (scope classification) resolve commands
through :func:`resolve_test_command`, so a command the detector recognises is
classifiable by construction — detection and classification are two readings of
one parse.

Matching is conservative by design. The raw command is normalised first —
compound-command segments, ``cd``/``source``/``.`` setup prefixes, leading
``VAR=value`` assignments, interpreter path prefixes (``.venv/bin/`` and
friends), and runner wrappers (``poetry run``, ``npx``, …) — and the runner
table then anchors on the normalised token head. Substring matching anywhere
in the raw string would match ``grep pytest`` or ``echo "run pytest"``; where
normalisation is ambiguous, the resolver returns ``None`` rather than guess.
"""

from __future__ import annotations

import re
import shlex

_SEPARATOR_RE = re.compile(r"&&|;|\|")
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Setup segments that may lead a compound command without being the command.
_SETUP_HEADS = {"cd", "source", "."}

# Wrappers that invoke a runner on their remaining arguments. Two-token
# wrappers first; one-token wrappers may carry leading flags (``npx -y jest``).
_WRAPPERS_TWO_TOKEN = {("poetry", "run"), ("uv", "run"), ("bundle", "exec")}
_WRAPPERS_ONE_TOKEN = {"npx", "time"}

# Bare names that may sit behind a ``*/bin/`` path prefix (`.venv/bin/python`,
# `./vendor/bin/phpunit`, `/usr/local/bin/vitest`).
_PATHABLE_HEADS = {
    "pytest", "python", "python3", "vitest", "jest", "rspec", "phpunit",
    "php", "dotnet", "gradle", "make", "npm", "yarn", "pnpm", "cargo", "go",
    "poetry", "uv", "npx", "bundle",
}

# Bound on wrapper nesting (`time npx poetry run …`) — anything deeper is
# treated as ambiguous and does not match.
_MAX_UNWRAP_DEPTH = 4


def resolve_test_command(command: str) -> tuple[str, list[str]] | None:
    """Resolve a shell command to ``(runner, args)``, or ``None``.

    ``runner`` is the canonical runner label (``"pytest"``,
    ``"python -m pytest"``, ``"make"``, ``"npm test"``, …); ``args`` are the
    tokens that follow the runner — the scope classification input. ``make``
    yields no path arguments: make targets are never paths.
    """
    tokens = _normalized_tokens(command)
    if not tokens:
        return None
    return _resolve_tokens(tokens)


def _normalized_tokens(command: str) -> list[str] | None:
    """Normalise a raw command to candidate runner tokens, or None."""
    segments = [seg.strip() for seg in _SEPARATOR_RE.split(command)]
    segments = [seg for seg in segments if seg]
    # Drop leading setup segments (`cd …`, `source …`, `. …`); the command of
    # interest is the last remaining segment.
    while segments and segments[0].split(None, 1)[0] in _SETUP_HEADS:
        segments.pop(0)
    if not segments:
        return None
    segment = segments[-1]
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    # Strip leading VAR=value assignments.
    while tokens and _ENV_ASSIGN_RE.match(tokens[0]):
        tokens.pop(0)
    return _strip_path_prefix(tokens)


def _strip_path_prefix(tokens: list[str]) -> list[str] | None:
    """Reduce a ``*/bin/<runner>`` head to the bare runner name.

    A path-prefixed head whose basename is not a recognised runner entry
    point (``./run_tests.sh``) yields None — never a match.
    """
    if not tokens:
        return None
    head = tokens[0]
    if "/" not in head:
        return tokens
    parts = head.split("/")
    if "bin" in parts[:-1] and parts[-1] in _PATHABLE_HEADS:
        return [parts[-1], *tokens[1:]]
    return None


def _resolve_tokens(tokens: list[str], depth: int = 0) -> tuple[str, list[str]] | None:
    """Match the runner table, unwrapping one wrapper layer per round."""
    if not tokens or depth > _MAX_UNWRAP_DEPTH:
        return None
    hit = _match_runner(tokens)
    if hit is not None:
        return hit
    unwrapped = _unwrap_once(tokens)
    if unwrapped is None:
        return None
    return _resolve_tokens(unwrapped, depth + 1)


def _unwrap_once(tokens: list[str]) -> list[str] | None:
    """Strip one wrapper layer, or None when the head is not a wrapper."""
    if len(tokens) >= 2 and (tokens[0], tokens[1]) in _WRAPPERS_TWO_TOKEN:
        rest = tokens[2:]
    elif tokens[0] in _WRAPPERS_ONE_TOKEN:
        rest = tokens[1:]
    else:
        return None
    while rest and rest[0].startswith("-"):
        rest = rest[1:]
    return rest


def _match_runner(tokens: list[str]) -> tuple[str, list[str]] | None:
    """Anchor the runner table on the normalised token head."""
    head, rest = tokens[0], tokens[1:]
    if head in ("python", "python3"):
        if rest[:2] == ["-m", "pytest"]:
            return "python -m pytest", rest[2:]
        if rest[:2] == ["-m", "unittest"]:
            return "python -m unittest", rest[2:]
        return None
    if head in ("pytest", "vitest", "jest", "rspec", "phpunit"):
        return head, rest
    if head == "php" and rest[:2] == ["artisan", "test"]:
        return "php artisan test", rest[2:]
    if head == "npm" and rest[:2] == ["run", "test"]:
        return "npm test", rest[2:]
    if head in ("dotnet", "gradle", "npm", "yarn", "pnpm", "cargo", "go") and rest[:1] == ["test"]:
        return f"{head} test", rest[1:]
    if head == "make":
        targets = [token for token in rest if not token.startswith("-")]
        if any(target in ("test", "validate") for target in targets):
            return "make", []
        return None
    return None

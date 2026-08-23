"""Failure taxonomy classifier and deterministic signature."""

from __future__ import annotations

import hashlib
import re
from enum import Enum


class FailureClass(str, Enum):
    """Taxonomy used by the night-shift circuit breaker and triage router."""

    ENVIRONMENT = "environment"
    FLAKY = "flaky"
    DESIGN = "design"
    TIMEOUT = "timeout"
    CANCELED = "canceled"


# Environment-side signals: missing tools/dependencies, network problems, auth.
# Keep these qualified — bare words like "missing" or "not found" match almost
# any real log tail and misclassify design failures as environmental.
_ENVIRONMENT_PATTERNS = [
    re.compile(r"\bcommand not found\b", re.IGNORECASE),
    re.compile(r"\bno such file or directory\b", re.IGNORECASE),
    re.compile(r"\bpermission denied\b", re.IGNORECASE),
    re.compile(r"\bconnection refused\b", re.IGNORECASE),
    re.compile(r"\bnetwork is unreachable\b", re.IGNORECASE),
    re.compile(r"\bcould not resolve\b", re.IGNORECASE),
    re.compile(r"\bgetaddrinfo\b", re.IGNORECASE),
    re.compile(r"\bssl\s+(?:error|certificate)\b", re.IGNORECASE),
    re.compile(r"\bauthentication failed\b", re.IGNORECASE),
    re.compile(r"\bunauthorized\b", re.IGNORECASE),
    re.compile(r"\bmodule not found\b", re.IGNORECASE),
    re.compile(r"\bno module named\b", re.IGNORECASE),
    re.compile(r"\bimport error\b", re.IGNORECASE),
    re.compile(r"\b(?:missing|unresolved) dependenc(?:y|ies)\b", re.IGNORECASE),
    re.compile(
        r"\bmissing\s+(?:module|package|command|tool|binary|executable)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcannot find\s+(?:module|package|command|tool|binary|executable|file)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bpackage not found\b", re.IGNORECASE),
]

# Design-side signals: test, assertion, type, lint failures.
_DESIGN_PATTERNS = [
    re.compile(r"\bFAILED\b"),
    re.compile(r"\bAssertionError\b"),
    re.compile(r"\bassertion failed\b", re.IGNORECASE),
    re.compile(r"\bassert\b", re.IGNORECASE),
    re.compile(r"\bTypeError\b"),
    re.compile(r"\bValueError\b"),
    re.compile(r"\bNameError\b"),
    re.compile(r"\bSyntaxError\b"),
    re.compile(r"\bIndentationError\b"),
    re.compile(r"\blint\b", re.IGNORECASE),
    re.compile(r"\bstyle\b", re.IGNORECASE),
]


def _matches_any(tail: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(pattern.search(tail) for pattern in patterns)


def classify(
    *,
    exit_code: int,
    tail: str,
    stage: str,
    verdict_recorded: bool,
    shutdown: bool,
    killed_by_timeout: bool,
) -> FailureClass:
    """Return the failure class for a finished session."""
    if shutdown:
        return FailureClass.CANCELED
    if killed_by_timeout:
        return FailureClass.TIMEOUT

    if _matches_any(tail, _ENVIRONMENT_PATTERNS):
        return FailureClass.ENVIRONMENT

    if verdict_recorded and _matches_any(tail, _DESIGN_PATTERNS):
        return FailureClass.DESIGN

    if exit_code != 0:
        return FailureClass.FLAKY

    return FailureClass.ENVIRONMENT


# Tokens that identify a line as the error key in a tail.
_ERROR_TOKENS = [
    "error",
    "failed",
    "assertion",
    "typeerror",
    "valueerror",
    "nameerror",
    "syntaxerror",
    "importerror",
    "modulenotfounderror",
    "connection",
    "refused",
    "authentication",
    "permission",
    "command not found",
]

# Regex substitutions applied after lower-casing. Order matters: UUIDs must be
# replaced before the generic hex pattern, and paths before line:col numbers.
_NORMALIZERS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
            r"(?:Z|[+-]\d{2}:?\d{2})?"
        ),
        "<timestamp>",
    ),
    (re.compile(r"\b\d{10,13}\b"), "<timestamp>"),
    (
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        ),
        "<uuid>",
    ),
    (re.compile(r"\b[0-9a-f]{6,}\b"), "<hex>"),
    (
        re.compile(
            r"(?:[~.]?[/\\]|[a-zA-Z]:\\\\|[a-zA-Z0-9_.\-]+[/\\])"
            r"[a-zA-Z0-9_.\-/\\]*"
        ),
        "<path>",
    ),
    (re.compile(r"\bpid\s+\d+\b", re.IGNORECASE), "<pid>"),
    (re.compile(r"\bline\s+\d+\b", re.IGNORECASE), "<linecol>"),
    (re.compile(r"\b\d+:\d+\b"), "<linecol>"),
]


def _extract_error_key(tail: str) -> str:
    """Return the most specific error line from *tail*."""
    lower_tail = tail.lower()
    lines = [line.strip() for line in lower_tail.splitlines() if line.strip()]
    for token in _ERROR_TOKENS:
        for line in reversed(lines):
            if token in line:
                return line
    return lines[-1] if lines else ""


def _normalize(key: str) -> str:
    for pattern, placeholder in _NORMALIZERS:
        key = pattern.sub(placeholder, key)
    return " ".join(key.split())


def signature(*, stage: str, tail: str) -> str:
    """Return a deterministic, stage-scoped signature for *tail*."""
    error_key = _normalize(_extract_error_key(tail))
    digest_input = f"{stage}\n{error_key}"
    return hashlib.sha1(digest_input.encode("utf-8")).hexdigest()[:12]

"""Regression test: retired CLI names must not reappear in source/docs/skills."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[2]

# Directories and files that document or invoke the CLI surface.
_SEARCH_ROOTS = [
    _REPO_ROOT / "skills",
    _REPO_ROOT / "docs",
    _REPO_ROOT / "src" / "aet" / "cli",
    _REPO_ROOT / ".agents" / "commands",
    _REPO_ROOT / ".agents" / "templates",
    _REPO_ROOT / "AGENTS.md",
]

# Files that legitimately discuss the retired names as part of this test.
_EXCLUDED_FILES = {
    _REPO_ROOT / "tests" / "cli" / "test_retired_names.py",
}

# Historical doc directories are allowed to reference the retired names; only
# active docs, skills, source, and command templates must keep the new surface.
_EXCLUDED_DIRS = {
    _REPO_ROOT / "docs" / "adr",
    _REPO_ROOT / "docs" / "plans",
    _REPO_ROOT / "docs" / "prds",
    _REPO_ROOT / "docs" / "audits",
    _REPO_ROOT / "docs" / "bugs",
    _REPO_ROOT / "docs" / "roadmaps",
    _REPO_ROOT / "docs" / "releases",
    _REPO_ROOT / "docs" / "retros",
    _REPO_ROOT / "docs" / "upgrades",
}


def _iter_files():
    for root in _SEARCH_ROOTS:
        if not root.exists():
            continue
        if root.is_file():
            if root not in _EXCLUDED_FILES:
                yield root
            continue
        for path in root.rglob("*"):
            if path.is_file() and path not in _EXCLUDED_FILES:
                # Skip binary/cache artifacts.
                if path.suffix in {".pyc", ".pyo", ".png", ".jpg", ".zip"}:
                    continue
                if "__pycache__" in path.parts:
                    continue
                if any(path.is_relative_to(d) for d in _EXCLUDED_DIRS):
                    continue
                yield path


def _token_before(text: str, start: int) -> str | None:
    prefix = text[:start].rstrip()
    match = re.search(r"(\S+)$", prefix)
    return match.group(1) if match else None


def _find_retired_occurrences() -> list[str]:
    occurrences = []

    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        # `aet plan` not followed by `validate`.
        for match in re.finditer(r"\baet\s+plan\b", text):
            end = match.end()
            rest = text[end:]
            # Whitespace + the word `validate` disqualifies the occurrence.
            if re.match(r"\s+validate\b", rest):
                continue
            occurrences.append(f"{path}:{_line_no(text, match.start())}: {match.group()}")

        # `aet review` not preceded by `gate`.
        for match in re.finditer(r"\baet\s+review\b", text):
            token = _token_before(text, match.start())
            if token == "gate":
                continue
            occurrences.append(f"{path}:{_line_no(text, match.start())}: {match.group()}")

        # `aet sync` not preceded by `queue`.
        for match in re.finditer(r"\baet\s+sync\b", text):
            token = _token_before(text, match.start())
            if token == "queue":
                continue
            occurrences.append(f"{path}:{_line_no(text, match.start())}: {match.group()}")

    return occurrences


def _line_no(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


class TestRetiredCliNames(unittest.TestCase):
    """ADR-039 retired several top-level command names; ensure they stay retired."""

    def test_no_retired_names_in_documented_surface(self):
        """``aet review``, bare ``aet plan``, and ``aet sync`` must not reappear."""
        occurrences = _find_retired_occurrences()
        if occurrences:
            self.fail(
                "Retired CLI names found in source/docs/skills:\n"
                + "\n".join(occurrences)
            )


if __name__ == "__main__":
    unittest.main()

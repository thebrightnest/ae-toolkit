#!/usr/bin/env python3
"""aet release-prep — Analyze commits since the last tag and suggest version bumps.

Outputs JSON with last tag, commits, version info, and suggested bump.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import typer

CONVENTIONAL_PATTERNS: list[tuple[str, str]] = [
    ("breaking", r"^[a-z]+\!:"),
    ("feature", r"^feat(\([^)]*\))?:"),
    ("feature", r"^feature(\([^)]*\))?:"),
    ("fix", r"^fix(\([^)]*\))?:"),
    ("fix", r"^bugfix(\([^)]*\))?:"),
    ("docs", r"^docs(\([^)]*\))?:"),
    ("chore", r"^chore(\([^)]*\))?:"),
    ("chore", r"^build(\([^)]*\))?:"),
    ("chore", r"^ci(\([^)]*\))?:"),
    ("refactor", r"^refactor(\([^)]*\))?:"),
    ("style", r"^style(\([^)]*\))?:"),
    ("test", r"^test(\([^)]*\))?:"),
    ("perf", r"^perf(\([^)]*\))?:"),
]

KEYWORD_PATTERNS: list[tuple[str, list[str]]] = [
    ("feature", [r"^add\b", r"new feature", r"^implement"]),
    ("fix", [r"^fix\b", r"bug"]),
    ("improvement", [r"^update\b", r"^improve\b"]),
    ("removal", [r"^remove\b", r"^delete\b"]),
]


class GitError(Exception):
    """Raised when a required git command fails."""


def _run_git(*args: str, cwd: Path | None = None) -> str:
    """Run a git command, swallowing stderr and returning stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.stdout.strip()


def detect_version_source(repo_root: Path | None = None) -> tuple[str, str]:
    """Detect the project's version source and current version.

    Resolution order: package.json, VERSION file, latest git tag, fallback 0.0.0.
    """
    root = repo_root or Path.cwd()

    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            ver = data.get("version")
            if ver:
                return ("package.json", str(ver))
        except (OSError, json.JSONDecodeError):
            pass

    version_file = root / "VERSION"
    if version_file.is_file():
        try:
            ver = version_file.read_text(encoding="utf-8").splitlines()[0].strip()
            if ver:
                return ("VERSION", ver)
        except OSError:
            pass

    tag = _run_git("describe", "--tags", "--abbrev=0", cwd=repo_root)
    if tag:
        return ("git-tag", tag)

    return ("none", "0.0.0")


def classify_commit(subject: str, body: str | None = None) -> str:
    """Classify a commit by conventional-commit prefix or keyword fallback."""
    subj_lower = subject.lower()
    body_lower = (body or "").lower()

    if "breaking change" in body_lower:
        return "breaking"

    for ctype, pattern in CONVENTIONAL_PATTERNS:
        if re.search(pattern, subj_lower):
            return ctype

    for ctype, patterns in KEYWORD_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, subj_lower):
                return ctype

    return "other"


def get_commits_since(ref: str | None = None, repo_root: Path | None = None) -> list[dict]:
    """Fetch commits since *ref* (or all commits if *ref* is empty)."""
    fmt = "%H|%s|%b---COMMIT_END---"
    if ref:
        args = ["log", f"{ref}..HEAD", f"--pretty=format:{fmt}"]
    else:
        args = ["log", f"--pretty=format:{fmt}"]

    raw = _run_git(*args, cwd=repo_root)
    if not raw:
        return []

    commits: list[dict] = []
    for record in raw.split("---COMMIT_END---"):
        record = record.strip()
        if not record:
            continue
        parts = record.split("|", 2)
        if len(parts) != 3:
            continue
        full_hash, subject, body = parts
        commits.append(
            {
                "hash": full_hash,
                "fullHash": full_hash,
                "subject": subject.strip(),
                "body": body.strip() or None,
            }
        )
    return commits


def determine_bump(commits: list[dict]) -> str:
    """Determine the semantic-version bump from classified commits."""
    has_breaking = any(c["type"] == "breaking" for c in commits)
    has_feature = any(c["type"] == "feature" for c in commits)
    has_fix = any(c["type"] in ("fix", "improvement") for c in commits)

    if has_breaking:
        return "major"
    if has_feature:
        return "minor"
    if has_fix:
        return "patch"
    return "patch"


def calculate_next_version(current: str, bump: str) -> str:
    """Calculate the next version from *current* and *bump*.

    Strips a leading "v" and strips prerelease identifiers (e.g. 1.0.0-beta3
    becomes 1.0.0).
    """
    if not current or current == "0.0.0":
        return "1.0.0"

    current = current.removeprefix("v")

    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(-.*)?$", current)
    if not match:
        return current

    major, minor, patch, prerelease = match.groups()
    major_i = int(major)
    minor_i = int(minor)
    patch_i = int(patch)

    if prerelease:
        return f"{major_i}.{minor_i}.{patch_i}"

    if bump == "major":
        return f"{major_i + 1}.0.0"
    if bump == "minor":
        return f"{major_i}.{minor_i + 1}.0"
    return f"{major_i}.{minor_i}.{patch_i + 1}"


def _count_by_type(commits: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {
        "breaking": 0,
        "feature": 0,
        "fix": 0,
        "improvement": 0,
        "docs": 0,
        "refactor": 0,
        "perf": 0,
        "chore": 0,
        "style": 0,
        "test": 0,
        "other": 0,
    }
    for commit in commits:
        ctype = commit.get("type", "other")
        counts[ctype] = counts.get(ctype, 0) + 1
    return counts


def _run(repo_root: Path) -> int:
    last_tag = _run_git("describe", "--tags", "--abbrev=0", cwd=repo_root) or None
    all_tags = _run_git("tag", "--list", "--sort=-v:refname", cwd=repo_root).splitlines()

    version_source, current_version = detect_version_source(repo_root)

    commits = get_commits_since(last_tag, repo_root)
    for commit in commits:
        commit["type"] = classify_commit(commit["subject"], commit.get("body"))

    bump = determine_bump(commits)
    next_version = calculate_next_version(current_version, bump)

    counts = _count_by_type(commits)

    output = {
        "lastTag": last_tag if last_tag else "(no tags)",
        "allTags": all_tags[:5],
        "currentVersion": current_version,
        "versionSource": version_source,
        "commitCount": len(commits),
        "commits": [
            {
                "hash": c["hash"][:8],
                "fullHash": c["fullHash"],
                "type": c["type"],
                "subject": c["subject"],
                "body": c.get("body"),
            }
            for c in commits
        ],
        "suggestedBump": bump,
        "nextVersion": next_version,
        "summary": {
            "breaking": counts["breaking"],
            "features": counts["feature"],
            "fixes": counts["fix"],
            "improvements": counts["improvement"],
            "docs": counts["docs"],
            "chores": counts["chore"] + counts["refactor"],
            "other": counts["other"] + counts["perf"] + counts["style"] + counts["test"],
        },
    }

    print(json.dumps(output, indent=2))
    return 0


app = typer.Typer(invoke_without_command=True)


@app.callback()
def release_prep(
    repo_root: Path | None = typer.Option(
        None,
        "--repo-root",
        help="Repository root (default: current working directory).",
    ),
) -> None:
    """Analyze commits since the last tag and suggest a version bump."""
    rc = _run(repo_root or Path.cwd())
    raise typer.Exit(rc)


def main(argv: list[str] | None = None) -> int:
    try:
        return app(argv or [], standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()

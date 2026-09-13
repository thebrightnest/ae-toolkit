#!/usr/bin/env python3
"""aet release-prep — Analyze commits since a baseline and suggest version bumps.

Outputs JSON describing the release window: the resolved baseline ref, the
commits in it, the project's version scheme, and where CHANGELOG/PRODUCT live.

Every resolution is configurable via the ``release_prep`` section of
``.agents/aet-config.json`` and auto-detected when absent, so the command works
in an unconfigured checkout and is exact in a configured one (ADR-077).
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
from pathlib import Path

import typer

try:  # tomllib is stdlib from 3.11; the package floor is 3.10 (pyproject.toml).
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python 3.10
    tomllib = None  # type: ignore[assignment]

CONFIG_PATH = ".agents/aet-config.json"

#: Version schemes. ``dated`` projects deploy continuously and never bump.
VERSION_SCHEMES = ("semver-tag", "semver-file", "dated")

#: Candidate locations probed when the config does not name a document path.
CHANGELOG_CANDIDATES = ("CHANGELOG.md", "docs/CHANGELOG.md", "content/CHANGELOG.md")
PRODUCT_CANDIDATES = ("docs/PRODUCT.md", "PRODUCT.md", "content/PRODUCT.md")

#: Used when no candidate exists yet — a first run creates the file here.
DEFAULT_CHANGELOG = "CHANGELOG.md"
DEFAULT_PRODUCT = "docs/PRODUCT.md"

#: A heading like ``## 2026-09-09`` (optionally a range) marks a dated changelog.
DATED_HEADING = re.compile(r"^##\s+\[?(\d{4}-\d{2}-\d{2})", re.MULTILINE)
#: A heading like ``## [1.2.3]`` or ``## v1.2.3`` marks a versioned changelog.
VERSIONED_HEADING = re.compile(r"^##\s+\[?v?\d+\.\d+\.\d+", re.MULTILINE)

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


def _git_ok(*args: str, cwd: Path | None = None) -> bool:
    """Return whether a git command exits zero, discarding its output."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.returncode == 0


def load_config(repo_root: Path | None = None) -> dict:
    """Read the ``release_prep`` section from ``.agents/aet-config.json``.

    A missing file, unreadable file, or malformed JSON yields an empty config so
    that every caller falls through to auto-detection rather than failing.
    """
    root = repo_root or Path.cwd()
    path = root / CONFIG_PATH
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    section = data.get("release_prep")
    return section if isinstance(section, dict) else {}


def _read_pyproject(root: Path) -> dict:
    """Parse ``pyproject.toml``, returning an empty mapping when absent/invalid.

    On Python 3.10, where ``tomllib`` does not exist, this returns ``{}`` and
    every caller falls through to the next resolution source rather than
    failing. The toolkit adds no TOML dependency for that one version (ADR-037).
    """
    path = root / "pyproject.toml"
    if tomllib is None or not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _uses_setuptools_scm(root: Path) -> bool:
    """Return whether the project derives its version from git tags via setuptools-scm.

    Requires both halves of the contract: ``version`` declared dynamic under
    ``[project]`` and a ``[tool.setuptools_scm]`` table. A project satisfying
    both has no version string to edit — the tag *is* the version.
    """
    data = _read_pyproject(root)
    if not data:
        return False
    dynamic = data.get("project", {}).get("dynamic") or []
    has_scm_table = "setuptools_scm" in data.get("tool", {})
    return "version" in dynamic and has_scm_table


def _version_from_file(root: Path, rel_path: str) -> str | None:
    """Read a version out of a known manifest format, by extension and name."""
    path = root / rel_path
    if not path.is_file():
        return None
    name = path.name
    try:
        if name == "pyproject.toml":
            data = _read_pyproject(path.parent)
            ver = data.get("project", {}).get("version")
            if not ver:
                ver = data.get("tool", {}).get("poetry", {}).get("version")
            return str(ver) if ver else None
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            ver = data.get("version") if isinstance(data, dict) else None
            return str(ver) if ver else None
        first = path.read_text(encoding="utf-8").splitlines()
        return first[0].strip() if first and first[0].strip() else None
    except (OSError, json.JSONDecodeError):
        return None


def detect_version_source(repo_root: Path | None = None, config: dict | None = None) -> tuple[str, str]:
    """Detect the project's version source and current version.

    A configured ``version_file`` wins outright. Otherwise setuptools-scm is
    checked first — a project whose version is dynamic has no file to edit
    regardless of what other manifests happen to sit beside it — then
    package.json, VERSION, pyproject, composer.json, the latest tag, and finally
    a ``0.0.0`` fallback.
    """
    root = repo_root or Path.cwd()
    cfg = config or {}

    configured = cfg.get("version_file")
    if configured:
        ver = _version_from_file(root, str(configured))
        if ver:
            return (str(configured), ver)

    if _uses_setuptools_scm(root):
        tag = _run_git("describe", "--tags", "--abbrev=0", cwd=repo_root)
        return ("setuptools-scm", tag or "0.0.0")

    package_json = root / "package.json"
    if package_json.is_file():
        ver = _version_from_file(root, "package.json")
        if ver:
            return ("package.json", ver)

    version_file = root / "VERSION"
    if version_file.is_file():
        ver = _version_from_file(root, "VERSION")
        if ver:
            return ("VERSION", ver)

    if (root / "pyproject.toml").is_file():
        ver = _version_from_file(root, "pyproject.toml")
        if ver:
            return ("pyproject.toml", ver)

    if (root / "composer.json").is_file():
        ver = _version_from_file(root, "composer.json")
        if ver:
            return ("composer.json", ver)

    tag = _run_git("describe", "--tags", "--abbrev=0", cwd=repo_root)
    if tag:
        return ("git-tag", tag)

    return ("none", "0.0.0")


def resolve_document_paths(repo_root: Path | None = None, config: dict | None = None) -> dict[str, dict[str, str]]:
    """Resolve where CHANGELOG.md and PRODUCT.md live for this repo.

    Config wins; otherwise the first existing candidate wins, so an established
    layout (``content/``, ``docs/``, or the root) is never relocated by a
    release run. With nothing on disk the defaults name where a first run should
    create each file.
    """
    root = repo_root or Path.cwd()
    cfg = config or {}

    def resolve(key: str, candidates: tuple[str, ...], default: str) -> dict[str, str]:
        configured = cfg.get(key)
        if configured:
            return {"path": str(configured), "origin": "config", "exists": (root / str(configured)).is_file()}
        for candidate in candidates:
            if (root / candidate).is_file():
                return {"path": candidate, "origin": "detected", "exists": True}
        return {"path": default, "origin": "default", "exists": False}

    return {
        "changelog": resolve("changelog_path", CHANGELOG_CANDIDATES, DEFAULT_CHANGELOG),
        "product": resolve("product_path", PRODUCT_CANDIDATES, DEFAULT_PRODUCT),
    }


def detect_version_scheme(
    repo_root: Path | None = None,
    config: dict | None = None,
    changelog_path: str | None = None,
    version_source: str | None = None,
) -> tuple[str, str]:
    """Resolve the version scheme, returning ``(scheme, reason)``.

    Config wins. Otherwise the existing changelog decides: a file whose newest
    heading is a date and which carries no version headings is a continuously
    deployed project that must not be handed a semver bump. Failing that, a
    dynamic (setuptools-scm) or tag-only version means ``semver-tag`` and an
    editable manifest means ``semver-file``.
    """
    root = repo_root or Path.cwd()
    cfg = config or {}

    configured = cfg.get("version_scheme")
    if configured in VERSION_SCHEMES:
        return (str(configured), "config")
    if configured:
        raise ValueError(f"Unknown version_scheme {configured!r}; expected one of {', '.join(VERSION_SCHEMES)}")

    if changelog_path:
        path = root / changelog_path
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                text = ""
            if DATED_HEADING.search(text) and not VERSIONED_HEADING.search(text):
                return ("dated", "changelog-headings-are-dates")

    if version_source in ("setuptools-scm", "git-tag", "none"):
        return ("semver-tag", f"version-source-{version_source}")

    return ("semver-file", f"version-source-{version_source}")


def reachable_tags(repo_root: Path | None = None) -> list[str]:
    """List tags that are ancestors of HEAD, newest version first.

    Tags that arrived with a vendored import or that live on an abandoned line
    of history are not ancestors of HEAD. ``git describe`` fails outright on
    such a repo, and treating that failure as "no tags" silently widens the
    release window to the whole history — so ancestry is filtered explicitly.
    """
    raw = _run_git("tag", "--list", "--merged", "HEAD", "--sort=-v:refname", cwd=repo_root)
    return [line.strip() for line in raw.splitlines() if line.strip()]


def unreachable_tags(repo_root: Path | None = None) -> list[str]:
    """List tags that exist but are not ancestors of HEAD, newest version first."""
    raw = _run_git("tag", "--list", "--no-merged", "HEAD", "--sort=-v:refname", cwd=repo_root)
    return [line.strip() for line in raw.splitlines() if line.strip()]


def last_changelog_commit(changelog_path: str, repo_root: Path | None = None) -> str | None:
    """Return the last commit that touched *changelog_path*, if any.

    This is the fallback baseline for a repo with no usable tag: whatever was
    last written to the changelog is, by construction, the last thing released.
    """
    root = repo_root or Path.cwd()
    if not (root / changelog_path).is_file():
        return None
    sha = _run_git("log", "-1", "--format=%H", "--", changelog_path, cwd=repo_root)
    return sha or None


def resolve_baseline(
    repo_root: Path | None = None,
    config: dict | None = None,
    since: str | None = None,
    changelog_path: str | None = None,
) -> tuple[str | None, str]:
    """Resolve the ref the release window starts from, as ``(ref, reason)``.

    Order: an explicit ``--since``, a configured ``baseline_ref``, the newest
    tag reachable from HEAD, the last commit that touched the changelog, then
    nothing — which means the whole history and a bootstrap run.
    """
    cfg = config or {}

    if since:
        if not _git_ok("rev-parse", "--verify", f"{since}^{{commit}}", cwd=repo_root):
            raise GitError(f"--since ref {since!r} does not resolve to a commit in this repository")
        return (since, "since-flag")

    configured = cfg.get("baseline_ref")
    if configured:
        if not _git_ok("rev-parse", "--verify", f"{configured}^{{commit}}", cwd=repo_root):
            raise GitError(
                f"Configured baseline_ref {configured!r} does not resolve to a commit; "
                f"fix it in {CONFIG_PATH} or pass --since"
            )
        return (str(configured), "config")

    tags = reachable_tags(repo_root)
    if tags:
        return (tags[0], "latest-reachable-tag")

    if changelog_path:
        sha = last_changelog_commit(changelog_path, repo_root)
        if sha:
            return (sha, "last-changelog-commit")

    return (None, "no-baseline")


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


def build_report(repo_root: Path, since: str | None = None) -> dict:
    """Assemble the full release-window report for *repo_root*."""
    config = load_config(repo_root)
    documents = resolve_document_paths(repo_root, config)
    changelog_path = documents["changelog"]["path"]

    version_source, current_version = detect_version_source(repo_root, config)
    scheme, scheme_reason = detect_version_scheme(repo_root, config, changelog_path, version_source)

    baseline, baseline_reason = resolve_baseline(repo_root, config, since, changelog_path)

    commits = get_commits_since(baseline, repo_root)
    for commit in commits:
        commit["type"] = classify_commit(commit["subject"], commit.get("body"))

    counts = _count_by_type(commits)
    stranded = unreachable_tags(repo_root)

    # A bootstrap run has no prior release to diff against: the changelog or
    # product doc is missing, or the window is the entire history. It calls for
    # seeding the documents, not appending one more entry to them.
    bootstrap = baseline is None or not documents["changelog"]["exists"] or not documents["product"]["exists"]

    if scheme == "dated":
        bump: str | None = None
        next_version: str | None = None
    else:
        bump = determine_bump(commits)
        next_version = calculate_next_version(current_version, bump)

    return {
        "baselineRef": baseline,
        "baselineReason": baseline_reason,
        "bootstrap": bootstrap,
        "configured": bool(config),
        "versionScheme": scheme,
        "versionSchemeReason": scheme_reason,
        "currentVersion": current_version,
        "versionSource": version_source,
        "releaseDate": _dt.date.today().isoformat(),
        "documents": documents,
        "reachableTags": reachable_tags(repo_root)[:5],
        "unreachableTags": stranded[:5],
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


def _run(repo_root: Path, since: str | None = None) -> int:
    try:
        report = build_report(repo_root, since)
    except (GitError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0


app = typer.Typer(invoke_without_command=True)


@app.callback()
def release_prep(
    repo_root: Path | None = typer.Option(
        None,
        "--repo-root",
        help="Repository root (default: current working directory).",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        help="Start the release window at this git ref, overriding tag and config resolution.",
    ),
) -> None:
    """Analyze commits since the last release and suggest a version bump."""
    rc = _run(repo_root or Path.cwd(), since)
    raise typer.Exit(rc)


def main(argv: list[str] | None = None) -> int:
    try:
        return app(argv or [], standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()

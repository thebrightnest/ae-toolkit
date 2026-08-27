"""Tests for the mechanical divergence computation at closure."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from aet import divergence, metrics, queue


def _init_repo(repo_root: str) -> None:
    """Initialize a git repo with a clean main branch."""
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.name", "Test User"],
        check=True,
    )
    Path(repo_root, "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "initial"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)


def _commit(repo_root: str, path: str, content: str, message: str) -> None:
    target = Path(repo_root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", path], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", message],
        check=True,
    )


def _make_merge_commit(
    repo_root: str,
    files: dict[str, str],
) -> str:
    """Create a feature branch with commits and squash-merge it to main."""
    subprocess.run(
        ["git", "-C", repo_root, "checkout", "-b", "feature"],
        check=True,
        capture_output=True,
    )
    for path, content in files.items():
        _commit(repo_root, path, content, f"add {path}")
    subprocess.run(
        ["git", "-C", repo_root, "checkout", "main"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "merge", "--squash", "feature"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "merge feature"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "branch", "-D", "feature"],
        check=True,
        capture_output=True,
    )
    proc = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _make_spec(declared_files: list[str]) -> dict[str, Any]:
    file_list = "\n".join(f"- `{f}`" for f in declared_files)
    body = f"""## Context
Some context.

## Files to Modify
{file_list}

## Tasks
1. Task 1
"""
    return {
        "frontmatter": {"id": "test-task", "size": "S"},
        "title": "Test Task",
        "body": body,
        "tasks": [{"id": 1, "text": "Task 1"}],
    }


def test_files_outside_the_declared_list_are_recorded(tmp_path: Path) -> None:
    repo_root = str(tmp_path / "repo")
    _init_repo(repo_root)

    merge_commit = _make_merge_commit(
        repo_root,
        {
            "src/a.py": "def a(): pass\n",
            "src/b.py": "def b(): pass\n",
            "tests/test_b.py": "def test_b(): pass\n",
        },
    )

    spec = _make_spec(["src/a.py"])
    result = divergence.compute_divergence(repo_root, merge_commit, spec=spec)

    assert result["status"] == "ok"
    assert result["reason"] is None
    assert sorted(result["files"]) == ["src/b.py", "tests/test_b.py"]


def test_no_divergence_is_empty_not_failed(tmp_path: Path) -> None:
    repo_root = str(tmp_path / "repo")
    _init_repo(repo_root)

    merge_commit = _make_merge_commit(
        repo_root,
        {
            "src/a.py": "def a(): pass\n",
            "tests/test_a.py": "def test_a(): pass\n",
        },
    )

    spec = _make_spec(["src/a.py", "tests/test_a.py"])
    result = divergence.compute_divergence(repo_root, merge_commit, spec=spec)

    assert result["status"] == "ok"
    assert result["reason"] is None
    assert result["files"] == []


def test_missing_first_parent_is_recorded_as_failed(tmp_path: Path) -> None:
    repo_root = str(tmp_path / "repo")
    _init_repo(repo_root)

    # Initial commit has no first parent (it is the root commit)
    proc = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    root_commit = proc.stdout.strip()

    spec = _make_spec(["src/a.py"])
    result = divergence.compute_divergence(repo_root, root_commit, spec=spec)

    assert result["status"] == "failed"
    assert result["files"] is None
    assert "first parent" in result["reason"]


def test_missing_merge_commit_is_recorded_as_failed(tmp_path: Path) -> None:
    repo_root = str(tmp_path / "repo")
    _init_repo(repo_root)

    spec = _make_spec(["src/a.py"])
    result = divergence.compute_divergence(repo_root, None, spec=spec)

    assert result["status"] == "failed"
    assert result["files"] is None
    assert result["reason"] == "no merge_commit recorded"


def test_missing_spec_is_recorded_as_failed(tmp_path: Path) -> None:
    repo_root = str(tmp_path / "repo")
    _init_repo(repo_root)

    merge_commit = _make_merge_commit(repo_root, {"src/a.py": "pass\n"})
    result = divergence.compute_divergence(repo_root, merge_commit, spec=None)

    assert result["status"] == "failed"
    assert result["files"] is None
    assert result["reason"] == "no spec recorded"


def test_docs_sync_skipped_still_records_divergence(tmp_path: Path) -> None:
    repo_root = str(tmp_path / "repo")
    _init_repo(repo_root)

    merge_commit = _make_merge_commit(
        repo_root,
        {
            "src/declared.py": "# declared\n",
            "src/extra.py": "# extra\n",
        },
    )

    spec = {
        "frontmatter": {
            "id": "task-with-skipped-docs",
            "size": "S",
            "docs_sync": "skipped",
            "docs_sync_reason": "trivial fix",
        },
        "title": "Task with skipped docs",
        "body": "## Files to Modify\n- `src/declared.py`\n",
        "tasks": [],
    }

    task = {
        "id": "task-with-skipped-docs",
        "merge_commit": merge_commit,
        "spec": spec,
    }

    history_file = Path(repo_root) / ".agents" / "work-history.jsonl"
    queue.append_history_record(str(history_file), task)

    with open(history_file, "r", encoding="utf-8") as f:
        recorded = json.loads(f.readline())

    assert "divergence" in recorded
    div = recorded["divergence"]
    assert div["status"] == "ok"
    assert div["files"] == ["src/extra.py"]


def test_closure_succeeds_when_divergence_computation_fails(tmp_path: Path) -> None:
    repo_root = str(tmp_path / "repo")
    _init_repo(repo_root)

    # Invalid merge commit
    task = {
        "id": "task-bad-commit",
        "merge_commit": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        "spec": _make_spec(["src/a.py"]),
    }

    history_file = Path(repo_root) / ".agents" / "work-history.jsonl"
    # Should not raise exception
    queue.append_history_record(str(history_file), task)

    with open(history_file, "r", encoding="utf-8") as f:
        recorded = json.loads(f.readline())

    assert "divergence" in recorded
    assert recorded["divergence"]["status"] == "failed"
    assert "first parent" in recorded["divergence"]["reason"]


def test_backfill_divergence_is_idempotent(tmp_path: Path) -> None:
    repo_root = str(tmp_path / "repo")
    _init_repo(repo_root)

    merge_commit = _make_merge_commit(
        repo_root,
        {"src/x.py": "x\n", "src/extra.py": "extra\n"},
    )
    spec = _make_spec(["src/x.py"])

    history_file = tmp_path / "history.jsonl"
    with open(history_file, "w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "id": "t1",
                    "merge_commit": merge_commit,
                    "spec": spec,
                    "settled_at": "2026-08-27T00:00:00Z",
                }
            )
            + "\n"
        )

    first = metrics.backfill_divergence(str(history_file), repo_root)
    assert first["measured"] == 1
    assert first["skipped"] == 0
    assert first["unresolvable"] == 0

    with open(history_file, "r", encoding="utf-8") as f:
        t1 = json.loads(f.readline())
    assert t1["divergence"]["status"] == "ok"
    assert t1["divergence"]["files"] == ["src/extra.py"]

    second = metrics.backfill_divergence(str(history_file), repo_root)
    assert second["measured"] == 0
    assert second["skipped"] == 1
    assert second["unresolvable"] == 0


def test_extract_declared_files_formatting() -> None:
    body = """## Files to Modify
- `src/foo.py`
* `src/bar.py` (new)
- [x] `src/baz.py` (NEW)
1. src/qux.py
- `src/dir/`
- `tests/test_foo.py`
"""
    files = divergence.extract_declared_files({"body": body})
    assert files == {
        "src/foo.py",
        "src/bar.py",
        "src/baz.py",
        "src/qux.py",
        "tests/test_foo.py",
    }


def test_divergence_with_test_delta(tmp_path: Path) -> None:
    repo_root = str(tmp_path / "repo")
    _init_repo(repo_root)

    merge_commit = _make_merge_commit(
        repo_root,
        {"src/a.py": "def a(): pass\n"},
    )
    spec = _make_spec(["src/a.py"])
    result = divergence.compute_divergence(
        repo_root, merge_commit, spec=spec, test_delta=5
    )

    assert result["status"] == "ok"
    assert result["files"] == []
    assert result["test_delta"] == 5


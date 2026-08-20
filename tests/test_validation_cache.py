"""Tests for the single-run validation cache."""

from __future__ import annotations

import json
from pathlib import Path

from aet import validation, validation_cache


class TestValidationCacheHash:
    """SHA-256 file hashing over source, test, and dependency files."""

    def test_empty_repo_has_stable_hash(self, tmp_path: Path):
        cache = validation_cache.ValidationCache(tmp_path)
        assert cache.compute_hash() == cache.compute_hash()

    def test_hash_includes_source_and_test_files(self, tmp_path: Path):
        (tmp_path / "src" / "aet").mkdir(parents=True)
        (tmp_path / "src" / "aet" / "foo.py").write_text("x")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_foo.py").write_text("y")
        (tmp_path / "pyproject.toml").write_text("z")

        cache = validation_cache.ValidationCache(tmp_path)
        assert cache.compute_hash()

    def test_hash_changes_when_source_file_changes(self, tmp_path: Path):
        (tmp_path / "src" / "aet").mkdir(parents=True)
        source = tmp_path / "src" / "aet" / "foo.py"
        source.write_text("x")
        (tmp_path / "tests").mkdir()
        (tmp_path / "pyproject.toml").write_text("z")

        cache = validation_cache.ValidationCache(tmp_path)
        before = cache.compute_hash()
        source.write_text("changed")
        after = cache.compute_hash()
        assert before != after

    def test_hash_changes_when_test_file_changes(self, tmp_path: Path):
        (tmp_path / "src" / "aet").mkdir(parents=True)
        (tmp_path / "src" / "aet" / "foo.py").write_text("x")
        (tmp_path / "tests").mkdir()
        test = tmp_path / "tests" / "test_foo.py"
        test.write_text("y")
        (tmp_path / "pyproject.toml").write_text("z")

        cache = validation_cache.ValidationCache(tmp_path)
        before = cache.compute_hash()
        test.write_text("changed")
        after = cache.compute_hash()
        assert before != after

    def test_hash_changes_when_pyproject_changes(self, tmp_path: Path):
        (tmp_path / "src" / "aet").mkdir(parents=True)
        (tmp_path / "src" / "aet" / "foo.py").write_text("x")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_foo.py").write_text("y")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("z")

        cache = validation_cache.ValidationCache(tmp_path)
        before = cache.compute_hash()
        pyproject.write_text("changed")
        after = cache.compute_hash()
        assert before != after

    def test_hash_includes_lockfile_if_present(self, tmp_path: Path):
        (tmp_path / "src" / "aet").mkdir(parents=True)
        (tmp_path / "src" / "aet" / "foo.py").write_text("x")
        (tmp_path / "tests").mkdir()
        (tmp_path / "pyproject.toml").write_text("z")

        cache = validation_cache.ValidationCache(tmp_path)
        before = cache.compute_hash()
        (tmp_path / "uv.lock").write_text("locked")
        after = cache.compute_hash()
        assert before != after

    def test_hash_ignores_untracked_files(self, tmp_path: Path):
        (tmp_path / "src" / "aet").mkdir(parents=True)
        (tmp_path / "src" / "aet" / "foo.py").write_text("x")
        (tmp_path / "tests").mkdir()
        (tmp_path / "pyproject.toml").write_text("z")

        cache = validation_cache.ValidationCache(tmp_path)
        before = cache.compute_hash()
        (tmp_path / "README.md").write_text("docs")
        (tmp_path / "docs").mkdir(parents=True)
        (tmp_path / "docs" / "plan.md").write_text("plan")
        after = cache.compute_hash()
        assert before == after


class TestValidationCacheStorage:
    """Cache entries are stored run-scoped and keyed by command + file hash."""

    def test_cache_miss_for_unknown_command(self, tmp_path: Path):
        cache = validation_cache.ValidationCache(tmp_path)
        assert cache.get("pytest tests/test_foo.py", "hash-1") is None

    def test_cache_hit_after_recording_result(self, tmp_path: Path):
        cache = validation_cache.ValidationCache(tmp_path)
        cache.set("pytest tests/test_foo.py", "hash-1", {"result": "passed"})
        assert cache.get("pytest tests/test_foo.py", "hash-1") == {"result": "passed"}

    def test_cache_miss_when_file_hash_changes(self, tmp_path: Path):
        cache = validation_cache.ValidationCache(tmp_path)
        cache.set("pytest tests/test_foo.py", "hash-1", {"result": "passed"})
        assert cache.get("pytest tests/test_foo.py", "hash-2") is None

    def test_cache_miss_when_command_changes(self, tmp_path: Path):
        cache = validation_cache.ValidationCache(tmp_path)
        cache.set("pytest tests/test_foo.py", "hash-1", {"result": "passed"})
        assert cache.get("pytest tests/test_bar.py", "hash-1") is None

    def test_cache_persists_to_disk(self, tmp_path: Path):
        cache = validation_cache.ValidationCache(tmp_path)
        cache.set("pytest tests/test_foo.py", "hash-1", {"result": "passed"})

        another = validation_cache.ValidationCache(tmp_path)
        assert another.get("pytest tests/test_foo.py", "hash-1") == {"result": "passed"}

    def test_cache_is_run_scoped(self, tmp_path: Path):
        run_a = validation_cache.ValidationCache.for_run(tmp_path, "run-a")
        run_b = validation_cache.ValidationCache.for_run(tmp_path, "run-b")

        run_a.set("pytest tests/test_foo.py", "hash-1", {"result": "passed"})
        assert run_b.get("pytest tests/test_foo.py", "hash-1") is None


class TestValidationModuleIntegration:
    """validation.py exposes the cache path and helpers."""

    def test_validation_cache_path(self):
        path = validation.validation_cache_path("/repo", "run-1")
        assert path == Path("/repo/.agents/runs/run-1/validation-cache.json")

    def test_get_validation_cache_returns_instance(self, tmp_path: Path):
        cache = validation.get_validation_cache(tmp_path, "run-1")
        assert isinstance(cache, validation_cache.ValidationCache)

    def test_get_validation_cache_uses_run_scoped_path(self, tmp_path: Path):
        cache = validation.get_validation_cache(tmp_path, "run-1")
        cache.set("pytest tests/test_foo.py", "hash-1", {"result": "passed"})

        expected_path = validation.validation_cache_path(tmp_path, "run-1")
        assert expected_path.exists()
        data = json.loads(expected_path.read_text(encoding="utf-8"))
        assert data["pytest tests/test_foo.py"]["hash-1"]["result"] == "passed"


class TestCachedValidationHelpers:
    """High-level helpers for checking and recording cached results."""

    def test_cached_result_returns_none_when_not_cached(self, tmp_path: Path):
        assert validation.cached_result("pytest tests/test_foo.py", tmp_path, "run-1") is None

    def test_cached_result_returns_stored_result(self, tmp_path: Path):
        validation.record_result(
            "pytest tests/test_foo.py",
            {"result": "passed"},
            tmp_path,
            "run-1",
        )
        assert validation.cached_result("pytest tests/test_foo.py", tmp_path, "run-1") == {"result": "passed"}

    def test_record_result_invalidates_on_different_hash(self, tmp_path: Path):
        validation.record_result(
            "pytest tests/test_foo.py",
            {"result": "passed"},
            tmp_path,
            "run-1",
        )
        assert validation.cached_result("pytest tests/test_foo.py", tmp_path, "run-1") == {"result": "passed"}

        # Simulate a file change by recording with a new hash.
        cache = validation.get_validation_cache(tmp_path, "run-1")
        assert cache.get("pytest tests/test_foo.py", "hash-2") is None

    def test_different_runs_do_not_share_cache(self, tmp_path: Path):
        validation.record_result(
            "pytest tests/test_foo.py",
            {"result": "passed"},
            tmp_path,
            "run-a",
        )
        assert validation.cached_result("pytest tests/test_foo.py", tmp_path, "run-b") is None

"""Tests for src/aet/boundary.py — the boundary-contract mechanical lens."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aet import boundary


class TestClassify:
    """Default pattern tables separate response-shape files from client consumers."""

    @pytest.mark.parametrize(
        "path",
        [
            "src/api/serializers/user_serializer.py",
            "src/controllers/user_controller.py",
            "src/schemas/user.json",
            "src/resources/user_resource.py",
            "src/dtos/user_dto.py",
            "app/serializers/user.py",
        ],
    )
    def test_default_shape_patterns_match(self, path: str):
        assert boundary._is_shape(path, boundary.DEFAULT_SHAPE_PATTERNS)

    @pytest.mark.parametrize(
        "path",
        [
            "src/components/user_list.tsx",
            "src/repositories/user_repository.py",
            "src/api-clients/user_client.ts",
            "src/hooks/useUser.ts",
            "src/stores/userStore.ts",
            "app/components/user.py",
        ],
    )
    def test_default_consumer_patterns_match(self, path: str):
        assert boundary._is_consumer(path, boundary.DEFAULT_CONSUMER_PATTERNS)

    def test_unrelated_paths_are_neither(self):
        assert not boundary._is_shape("src/utils/helpers.py", boundary.DEFAULT_SHAPE_PATTERNS)
        assert not boundary._is_consumer("src/utils/helpers.py", boundary.DEFAULT_CONSUMER_PATTERNS)


class TestConfigOverride:
    """The lens reads per-project overrides from .agents/aet-config.json."""

    def test_config_override_replaces_default_patterns(self, tmp_path: Path):
        config = {
            "boundary_contract": {
                "shape_patterns": ["contract"],
                "consumer_patterns": ["adapter"],
                "marker_vocabulary": ["wiremock"],
            }
        }
        repo_root = tmp_path / "repo"
        agents_dir = repo_root / ".agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "aet-config.json").write_text(json.dumps(config), encoding="utf-8")

        result = boundary.check(
            ["src/contract/user.py", "src/adapter/user.py"],
            repo_root=repo_root,
        )
        assert result.tripped
        assert result.shape_paths == ["src/contract/user.py"]
        assert result.consumer_paths == ["src/adapter/user.py"]

    def test_missing_config_file_uses_defaults(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        result = boundary.check(
            ["src/serializers/user.py", "src/components/user.tsx"],
            repo_root=repo_root,
        )
        assert result.tripped


class TestPairing:
    """The lens fires only when the changed set touches both sides of the contract."""

    def test_fires_when_both_shape_and_consumer_changed(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        result = boundary.check(
            ["src/serializers/user.py", "src/components/user.tsx"],
            repo_root=repo_root,
        )
        assert result.tripped
        assert result.reason == "shape-consumer pair(s) changed without agreement test"
        assert result.pairs == [("src/serializers/user.py", "src/components/user.tsx")]

    def test_does_not_fire_when_only_shape_changed(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        result = boundary.check(["src/serializers/user.py"], repo_root=repo_root)
        assert not result.tripped
        assert result.shape_paths == ["src/serializers/user.py"]
        assert result.consumer_paths == []

    def test_does_not_fire_when_only_consumer_changed(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        result = boundary.check(["src/components/user.tsx"], repo_root=repo_root)
        assert not result.tripped
        assert result.shape_paths == []
        assert result.consumer_paths == ["src/components/user.tsx"]

    def test_does_not_fire_when_neither_side_changed(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        result = boundary.check(["src/utils/helpers.py"], repo_root=repo_root)
        assert not result.tripped

    def test_empty_paths_do_not_fire(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        assert not boundary.check([], repo_root=repo_root).tripped

    def test_none_paths_do_not_fire(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        assert not boundary.check(None, repo_root=repo_root).tripped


class TestAgreementTestDetection:
    """An agreement test satisfies the lens by referencing both sides or using markers."""

    def test_agreement_test_by_module_reference(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        tests_dir = repo_root / "tests"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_user_boundary.py"
        test_file.write_text(
            "def test_user_serializer_matches_component():\n"
            "    from src.serializers.user import UserSerializer\n"
            "    from src.components.user import UserComponent\n"
            "    assert True\n",
            encoding="utf-8",
        )

        result = boundary.check(
            ["src/serializers/user.py", "src/components/user.py"],
            repo_root=repo_root,
        )
        assert not result.tripped
        assert result.agreement_tests == ["tests/test_user_boundary.py"]

    def test_agreement_test_by_marker_vocabulary(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        tests_dir = repo_root / "tests"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_user_api.py"
        test_file.write_text(
            "import msw\n"
            "def test_user_api():\n"
            "    pass\n",
            encoding="utf-8",
        )

        result = boundary.check(
            ["src/serializers/user.py", "src/components/user.tsx"],
            repo_root=repo_root,
        )
        assert not result.tripped
        assert result.agreement_tests == ["tests/test_user_api.py"]

    def test_no_agreement_test_found_trips_lens(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        tests_dir = repo_root / "tests"
        tests_dir.mkdir(parents=True)
        # A test that only references one side is not an agreement test.
        (tests_dir / "test_shape_only.py").write_text(
            "def test_serializer(): pass\n", encoding="utf-8"
        )

        result = boundary.check(
            ["src/serializers/user.py", "src/components/user.tsx"],
            repo_root=repo_root,
        )
        assert result.tripped
        assert result.agreement_tests == []

    def test_any_agreement_test_satisfies_all_pairs(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        tests_dir = repo_root / "tests"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_boundary.py"
        test_file.write_text(
            "def test_both():\n"
            "    from src.serializers.user import UserSerializer\n"
            "    from src.components.user import UserComponent\n"
            "    pass\n",
            encoding="utf-8",
        )

        result = boundary.check(
            [
                "src/serializers/user.py",
                "src/serializers/order.py",
                "src/components/user.tsx",
                "src/components/order.tsx",
            ],
            repo_root=repo_root,
        )
        assert not result.tripped
        # A single agreement test is enough to satisfy the lens.
        assert result.agreement_tests == ["tests/test_boundary.py"]


class TestResultStructure:
    """The result object reports every detail the gate needs."""

    def test_result_fields_are_populated(self, tmp_path: Path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        result = boundary.check(
            ["src/schemas/user.py", "src/repositories/user_repo.py"],
            repo_root=repo_root,
        )
        assert result.tripped
        assert result.shape_paths == ["src/schemas/user.py"]
        assert result.consumer_paths == ["src/repositories/user_repo.py"]
        assert result.pairs == [("src/schemas/user.py", "src/repositories/user_repo.py")]
        assert result.agreement_tests == []
        assert "agreement test" in result.reason.lower()

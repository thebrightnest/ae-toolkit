"""Tests for src/aet/identity.py — the identity-conflation mechanical lens."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from aet import identity


class TestExtractIdentifiers:
    """The lens recognises each identifier shape listed in the plan."""

    @pytest.mark.parametrize(
        "line, expected",
        [
            ("projectId = 1", [("projectId", "project", "id")]),
            ("projectID = 1", [("projectID", "project", "id")]),
            ("projectUuid = 'u'", [("projectUuid", "project", "uuid")]),
            ("projectUUID = 'u'", [("projectUUID", "project", "uuid")]),
            ("project_id = 1", [("project_id", "project", "id")]),
            ("project_uuid = 'u'", [("project_uuid", "project", "uuid")]),
            ("projectPath = '/x'", [("projectPath", "project", "path")]),
        ],
    )
    def test_identifier_shape_extraction(self, line: str, expected: list[tuple[str, str, str]]):
        idents = identity._extract_identifiers([line])
        assert [(i.name, i.stem, i.kind) for i in idents] == expected

    def test_route_param_bindings_are_captured(self):
        idents = identity._extract_identifiers(['const route = "/projects/{projectId}/items";'])
        assert [(i.name, i.stem, i.kind) for i in idents] == [("projectId", "project", "id")]

    def test_colon_route_params_are_captured(self):
        idents = identity._extract_identifiers(['app.get("/users/:user_uuid")'])
        assert [(i.name, i.stem, i.kind) for i in idents] == [("user_uuid", "user", "uuid")]

    def test_bare_id_words_are_ignored(self):
        idents = identity._extract_identifiers(["id = 1", "uuid = 2", "valid = True"])
        assert not idents

    def test_uuid_generator_like_words_are_ignored(self):
        idents = identity._extract_identifiers(["class UUIDGenerator:", "def getUUIDHelper():"])
        assert not idents


class TestConflationDetection:
    """Identifiers group by stem; two distinct kinds for one stem fire the lens."""

    def test_single_identifier_does_not_fire(self):
        idents = identity._extract_identifiers(["projectId = 1"])
        assert identity._conflated_entities(idents) == []

    def test_two_id_kinds_for_same_stem_fire(self):
        idents = identity._extract_identifiers(["projectId = 1", "projectPath = '/x'"])
        entities = identity._conflated_entities(idents)
        assert len(entities) == 1
        assert entities[0]["entity"] == "project"
        assert set(entities[0]["kinds"]) == {"id", "path"}

    def test_distinct_stems_do_not_conflate(self):
        idents = identity._extract_identifiers(["userId = 1", "projectPath = '/x'"])
        assert identity._conflated_entities(idents) == []

    def test_casing_variants_collapse_to_one_kind(self):
        idents = identity._extract_identifiers(["projectId = 1", "projectID = 2"])
        assert identity._conflated_entities(idents) == []


class TestDiffScanning:
    """The lens scans added lines of the diff against the configured base ref."""

    @pytest.fixture
    def repo(self, tmp_path: Path):
        """A temp git repo with an ``origin/main`` branch for the base ref."""
        root = tmp_path / "repo"
        root.mkdir()
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        src = root / "src" / "api.py"
        src.parent.mkdir(parents=True)
        src.write_text("# initial\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        # Create a local branch literally named origin/main to satisfy BASE_REF.
        subprocess.run(
            ["git", "branch", "origin/main"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        return root

    def _edit(self, repo: Path, content: str):
        src = repo / "src" / "api.py"
        src.write_text(content, encoding="utf-8")

    def test_path_vs_uuid_pair(self, repo: Path):
        self._edit(repo, "projectPath = '/x'\nprojectUuid = 'u'\n")
        result = identity.check(["src/api.py"], repo_root=repo)
        assert result.tripped
        assert any(
            e["entity"] == "project" and set(e["kinds"]) == {"path", "uuid"}
            for e in result.findings
        )

    def test_session_id_vs_session_uuid_pair(self, repo: Path):
        self._edit(repo, "sessionId = 'provider'\nsessionUuid = 'app'\n")
        result = identity.check(["src/api.py"], repo_root=repo)
        assert result.tripped
        assert any(e["entity"] == "session" for e in result.findings)

    def test_project_path_vs_project_id_pair(self, repo: Path):
        self._edit(repo, "projectPath = '/x'\nprojectId = 1\n")
        result = identity.check(["src/api.py"], repo_root=repo)
        assert result.tripped
        assert any(
            e["entity"] == "project" and set(e["kinds"]) == {"id", "path"}
            for e in result.findings
        )

    def test_route_param_vs_resolved_id(self, repo: Path):
        self._edit(
            repo,
            '@app.get("/projects/{projectId}")\n'
            "def get(projectUuid: str):\n"
            "    pass\n",
        )
        result = identity.check(["src/api.py"], repo_root=repo)
        assert result.tripped
        assert any(e["entity"] == "project" for e in result.findings)

    def test_single_identifier_does_not_trip(self, repo: Path):
        self._edit(repo, "projectId = 1\n")
        result = identity.check(["src/api.py"], repo_root=repo)
        assert not result.tripped
        assert result.findings == []

    def test_no_changed_paths_does_not_trip(self, repo: Path):
        result = identity.check([], repo_root=repo)
        assert not result.tripped

    def test_undeterminable_diff_is_indeterminate(self, repo: Path):
        result = identity.check(["src/api.py"], repo_root=repo, base_ref="nonexistent/ref")
        assert result.tripped
        assert result.indeterminate


class TestDeclarationValidation:
    """A valid ``identity:`` frontmatter block satisfies a fired lens."""

    @pytest.fixture
    def repo_with_plan(self, tmp_path: Path):
        root = tmp_path / "repo"
        root.mkdir()
        plans_dir = root / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "t2r-09-identity-conflation-lens.md"
        plan.write_text(
            "---\n"
            "id: t2r-09-identity-conflation-lens\n"
            "size: M\n"
            "---\n\n"
            "# Plan\n",
            encoding="utf-8",
        )
        return root

    def _write_plan(self, root: Path, identity_block: Any):
        from aet import plan_parser

        plan = root / "docs" / "plans" / "t2r-09-identity-conflation-lens.md"
        data = plan_parser.parse_frontmatter(plan)
        data["identity"] = identity_block

        # plan_parser normalizes block-style list items as scalars, so write
        # the identity declaration as a flow-style collection to keep it valid.
        def _flow_identity(entries: list[dict[str, Any]]) -> str:
            items: list[str] = []
            for entry in entries:
                idents = ", ".join(f'"{i}"' for i in entry["identifiers"])
                items.append(
                    f'{{entity: {entry["entity"]}, identifiers: [{idents}], '
                    f'persists: {entry["persists"]}}}'
                )
            return f'identity: [{", ".join(items)}]'

        lines = ["---"]
        for key, value in data.items():
            if key == "identity":
                lines.append(_flow_identity(identity_block))
            elif isinstance(value, list):
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}: {value}")
        lines.append("---\n\n# Plan\n")
        plan.write_text("\n".join(lines), encoding="utf-8")

    def test_valid_declaration_satisfies_lens(self, repo_with_plan: Path):
        self._write_plan(
            repo_with_plan,
            [
                {
                    "entity": "project",
                    "identifiers": ["projectId", "projectPath"],
                    "persists": "projectId",
                }
            ],
        )
        entities = [
            {"entity": "project", "identifiers": ["projectId", "projectPath"], "kinds": ["id", "path"]}
        ]
        valid, errors, findings = identity._validate_declarations(
            repo_with_plan / "docs" / "plans" / "t2r-09-identity-conflation-lens.md",
            entities,
        )
        assert valid
        assert not errors
        assert findings[0]["persists"] == "projectId"

    def test_missing_declaration_is_invalid(self, repo_with_plan: Path):
        entities = [
            {"entity": "project", "identifiers": ["projectId", "projectPath"], "kinds": ["id", "path"]}
        ]
        valid, errors, _findings = identity._validate_declarations(
            repo_with_plan / "docs" / "plans" / "t2r-09-identity-conflation-lens.md",
            entities,
        )
        assert not valid
        assert any("no identity: block" in e for e in errors)

    def test_declaration_with_one_identifier_is_invalid(self, repo_with_plan: Path):
        self._write_plan(
            repo_with_plan,
            [
                {
                    "entity": "project",
                    "identifiers": ["projectId"],
                    "persists": "projectId",
                }
            ],
        )
        entities = [
            {"entity": "project", "identifiers": ["projectId", "projectPath"], "kinds": ["id", "path"]}
        ]
        valid, errors, _findings = identity._validate_declarations(
            repo_with_plan / "docs" / "plans" / "t2r-09-identity-conflation-lens.md",
            entities,
        )
        assert not valid
        assert any("at least two strings" in e for e in errors)

    def test_persists_not_among_identifiers_is_invalid(self, repo_with_plan: Path):
        self._write_plan(
            repo_with_plan,
            [
                {
                    "entity": "project",
                    "identifiers": ["projectId", "projectPath", "projectUuid"],
                    "persists": "projectUuid",
                }
            ],
        )
        entities = [
            {"entity": "project", "identifiers": ["projectId", "projectPath"], "kinds": ["id", "path"]}
        ]
        valid, errors, _findings = identity._validate_declarations(
            repo_with_plan / "docs" / "plans" / "t2r-09-identity-conflation-lens.md",
            entities,
        )
        assert not valid
        assert any("persists" in e and "not among" in e for e in errors)


class TestCheckIntegration:
    """``identity.check`` combines diff scanning and declaration validation."""

    @pytest.fixture
    def repo(self, tmp_path: Path):
        root = tmp_path / "repo"
        root.mkdir()
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        src = root / "src" / "api.py"
        src.parent.mkdir(parents=True)
        src.write_text("# initial\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "origin/main"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        plans_dir = root / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        return root

    def _write_plan(self, root: Path, content: str):
        plan = root / "docs" / "plans" / "t2r-09-identity-conflation-lens.md"
        plan.write_text(content, encoding="utf-8")

    def test_fired_undeclared_lens_trips(self, repo: Path):
        src = repo / "src" / "api.py"
        src.write_text("projectId = 1\nprojectPath = '/x'\n", encoding="utf-8")
        result = identity.check(
            ["src/api.py"],
            repo_root=repo,
            task_id="t2r-09-identity-conflation-lens",
        )
        assert result.tripped
        assert not result.declaration_valid

    def test_fired_declared_lens_does_not_trip(self, repo: Path):
        src = repo / "src" / "api.py"
        src.write_text("projectId = 1\nprojectPath = '/x'\n", encoding="utf-8")
        self._write_plan(
            repo,
            "---\n"
            "id: t2r-09-identity-conflation-lens\n"
            "size: M\n"
            'identity: [{entity: project, identifiers: ["projectId", "projectPath"], persists: projectId}]\n'
            "---\n\n"
            "# Plan\n",
        )
        result = identity.check(
            ["src/api.py"],
            repo_root=repo,
            task_id="t2r-09-identity-conflation-lens",
        )
        assert not result.tripped
        assert result.declaration_valid
        assert result.findings[0]["persists"] == "projectId"

    def test_fired_malformed_declaration_trips(self, repo: Path):
        src = repo / "src" / "api.py"
        src.write_text("projectId = 1\nprojectPath = '/x'\n", encoding="utf-8")
        self._write_plan(
            repo,
            "---\n"
            "id: t2r-09-identity-conflation-lens\n"
            "size: M\n"
            'identity: [{entity: project, identifiers: ["projectId"], persists: projectId}]\n'
            "---\n\n"
            "# Plan\n",
        )
        result = identity.check(
            ["src/api.py"],
            repo_root=repo,
            task_id="t2r-09-identity-conflation-lens",
        )
        assert result.tripped
        assert not result.declaration_valid

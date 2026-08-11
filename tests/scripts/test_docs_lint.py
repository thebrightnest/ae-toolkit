"""Tests for the ``aet docs lint`` rule engine and CLI."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from aet import docs_lint

REPO_ROOT = Path(__file__).parents[2]
MAIN_PY = REPO_ROOT / "src" / "aet" / "cli" / "main.py"
MAKEFILE = REPO_ROOT / "Makefile"


def _write_rules(path: Path, rules: list[dict]) -> None:
    import yaml

    path.write_text(yaml.safe_dump({"rules": rules}), encoding="utf-8")


def test_must_contain_passes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    doc = repo / "README.md"
    doc.write_text("# Toolkit\n\nAgentic Engineering Toolkit\n", encoding="utf-8")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "must_contain", "target": "README.md", "value": "Agentic", "reason": "README must name the toolkit"}],
    )

    assert docs_lint.lint_docs(rules, repo) == []


def test_must_contain_fails_with_reason_and_value(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    doc = repo / "README.md"
    doc.write_text("# Toolkit\n", encoding="utf-8")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [
            {
                "type": "must_contain",
                "target": "README.md",
                "value": "Engineering",
                "reason": "README must mention Engineering",
            }
        ],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert violations[0][0].name == "README.md"
    assert "README must mention Engineering" in violations[0][1]
    assert "'Engineering'" in violations[0][1]


def test_must_contain_list_requires_all(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    doc = repo / "README.md"
    doc.write_text("# Toolkit\n\nOne\n", encoding="utf-8")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [
            {
                "type": "must_contain",
                "target": "README.md",
                "value": ["One", "Two"],
                "reason": "README must list both items",
            }
        ],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "'Two'" in violations[0][1]


def test_must_not_contain_passes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    doc = repo / "README.md"
    doc.write_text("# Toolkit\n\nClean prose.\n", encoding="utf-8")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [
            {
                "type": "must_not_contain",
                "target": "README.md",
                "value": "TODO",
                "reason": "README must not contain TODO",
            }
        ],
    )

    assert docs_lint.lint_docs(rules, repo) == []


def test_must_not_contain_fails_with_reason_and_value(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    doc = repo / "README.md"
    doc.write_text("# Toolkit\n\nTODO: fix me\n", encoding="utf-8")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [
            {
                "type": "must_not_contain",
                "target": "README.md",
                "value": "TODO",
                "reason": "README must not contain TODO",
            }
        ],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "README must not contain TODO" in violations[0][1]
    assert "'TODO'" in violations[0][1]


def test_section_scoped_must_contain_passes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    doc = repo / "README.md"
    doc.write_text(
        "# Toolkit\n\n## Context\n\nimportant detail\n\n## Other\n\nnoise\n",
        encoding="utf-8",
    )
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [
            {
                "type": "must_contain",
                "target": "README.md",
                "section": "Context",
                "value": "important detail",
                "reason": "Context section must mention the detail",
            }
        ],
    )

    assert docs_lint.lint_docs(rules, repo) == []


def test_section_scoped_must_contain_fails_when_section_missing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    doc = repo / "README.md"
    doc.write_text("# Toolkit\n\n## Other\n\ncontent\n", encoding="utf-8")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [
            {
                "type": "must_contain",
                "target": "README.md",
                "section": "Context",
                "value": "detail",
                "reason": "Context section must mention the detail",
            }
        ],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "section not found: Context" in violations[0][1]


def test_section_scoped_must_not_contain_ignores_other_sections(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    doc = repo / "README.md"
    doc.write_text(
        "# Toolkit\n\n## Context\n\nclean prose\n\n## Other\n\nFORBIDDEN\n",
        encoding="utf-8",
    )
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [
            {
                "type": "must_not_contain",
                "target": "README.md",
                "section": "Context",
                "value": "FORBIDDEN",
                "reason": "Context section must stay clean",
            }
        ],
    )

    assert docs_lint.lint_docs(rules, repo) == []


def test_path_exists_passes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").mkdir()
    (repo / "docs" / "adr").mkdir()
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "path_exists", "target": "docs/adr", "reason": "ADR directory must exist"}],
    )

    assert docs_lint.lint_docs(rules, repo) == []


def test_path_exists_fails(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "path_exists", "target": "docs/adr", "reason": "ADR directory must exist"}],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "ADR directory must exist" in violations[0][1]
    assert "expected path to exist" in violations[0][1]


def test_path_absent_passes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "path_absent", "target": "legacy.md", "reason": "Legacy file must be retired"}],
    )

    assert docs_lint.lint_docs(rules, repo) == []


def test_path_absent_fails(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "legacy.md").write_text("old\n", encoding="utf-8")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "path_absent", "target": "legacy.md", "reason": "Legacy file must be retired"}],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "Legacy file must be retired" in violations[0][1]
    assert "expected path to be absent" in violations[0][1]


def test_missing_target_file_fails_closed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "must_contain", "target": "MISSING.md", "value": "x", "reason": "Missing target should fail"}],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "Missing target should fail" in violations[0][1]
    assert "target file missing" in violations[0][1]


def test_malformed_rules_file_fails(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    rules = repo / "rules.yaml"
    rules.write_text("not: [valid yaml: :\n", encoding="utf-8")

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "invalid YAML" in violations[0][1]


def test_missing_reason_fails(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    rules = repo / "rules.yaml"
    _write_rules(rules, [{"type": "must_contain", "target": "x.md", "value": "x"}])

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "missing required fields: reason" in violations[0][1]


def test_unknown_rule_type_fails(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "must_frobnicate", "target": "x.md", "value": "x", "reason": "bad type"}],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "unknown type 'must_frobnicate'" in violations[0][1]


def _write_adr(path: Path, frontmatter: dict | None, body: str = "# ADR\n") -> None:
    if frontmatter is None:
        path.write_text(body, encoding="utf-8")
    else:
        import yaml

        fm = yaml.safe_dump(frontmatter).strip()
        path.write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")


def test_unique_live_subject_fails_on_dual_live(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    _write_adr(adr_dir / "011-state.md", {"subject": "state"}, "# ADR-011\n")
    _write_adr(adr_dir / "012-state.md", {"subject": "state"}, "# ADR-012\n")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "unique_live_subject", "target": "docs/adr", "reason": "One live rule per subject"}],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "subject 'state' has multiple live ADRs" in violations[0][1]
    assert "ADR-011" in violations[0][1]
    assert "ADR-012" in violations[0][1]


def test_unique_live_subject_passes_when_superseded(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    _write_adr(adr_dir / "010-state.md", {"subject": "state"}, "# ADR-010\n")
    _write_adr(adr_dir / "011-state.md", {"subject": "state", "supersedes": [10]}, "# ADR-011\n")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "unique_live_subject", "target": "docs/adr", "reason": "One live rule per subject"}],
    )

    assert docs_lint.lint_docs(rules, repo) == []


def test_unique_live_subject_ignores_adr_without_frontmatter(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    _write_adr(adr_dir / "011-state.md", {"subject": "state"}, "# ADR-011\n")
    _write_adr(adr_dir / "012-nofm.md", None, "# ADR-012\n")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "unique_live_subject", "target": "docs/adr", "reason": "One live rule per subject"}],
    )

    assert docs_lint.lint_docs(rules, repo) == []


def test_unique_live_subject_fails_on_malformed_frontmatter(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    adr = adr_dir / "011-state.md"
    adr.write_text("---\nnot: [valid yaml: :\n---\n# ADR-011\n", encoding="utf-8")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "unique_live_subject", "target": "docs/adr", "reason": "One live rule per subject"}],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "malformed frontmatter" in violations[0][1]


def test_unique_live_subject_excludes_template_and_readme(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    _write_adr(adr_dir / "000-template.md", {"subject": "state"}, "# Template\n")
    _write_adr(adr_dir / "README.md", {"subject": "state"}, "# README\n")
    _write_adr(adr_dir / "011-state.md", {"subject": "state"}, "# ADR-011\n")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "unique_live_subject", "target": "docs/adr", "reason": "One live rule per subject"}],
    )

    assert docs_lint.lint_docs(rules, repo) == []


def test_unique_live_subject_accepts_string_or_list_subject(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    _write_adr(adr_dir / "011-state.md", {"subject": "state"}, "# ADR-011\n")
    _write_adr(adr_dir / "012-other.md", {"subject": ["other"]}, "# ADR-012\n")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "unique_live_subject", "target": "docs/adr", "reason": "One live rule per subject"}],
    )

    assert docs_lint.lint_docs(rules, repo) == []


def test_unique_live_subject_fails_on_invalid_subject_type(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    _write_adr(adr_dir / "011-state.md", {"subject": 123}, "# ADR-011\n")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [{"type": "unique_live_subject", "target": "docs/adr", "reason": "One live rule per subject"}],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert "'subject' must be a string or list" in violations[0][1]


def test_must_not_contain_on_directory_scans_all_markdown_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    skills = repo / "skills"
    skills.mkdir()
    clean = skills / "clean.md"
    clean.write_text("# Clean\n", encoding="utf-8")
    bad_dir = skills / "bad"
    bad_dir.mkdir()
    bad = bad_dir / "bad.md"
    bad.write_text("# Bad\n\ncommit the plan files\n", encoding="utf-8")
    rules = repo / "rules.yaml"
    _write_rules(
        rules,
        [
            {
                "type": "must_not_contain",
                "target": "skills",
                "value": "commit the plan files",
                "reason": "Skills must not instruct committing plan files at intake",
            }
        ],
    )

    violations = docs_lint.lint_docs(rules, repo)
    assert len(violations) == 1
    assert violations[0][0].name == "bad.md"
    assert "commit the plan files" in violations[0][1]


def test_cli_dispatcher_routes_docs_lint(tmp_path):
    """``aet docs lint`` runs through the dispatcher and exits 0 on a clean repo."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    rules = repo / ".agents" / "doc-rules.yaml"
    rules.parent.mkdir(parents=True)
    rules.write_text("rules: []\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(MAIN_PY), "docs", "lint"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "docs lint passed" in result.stdout


def test_cli_dispatcher_fails_gate_on_rule_violation(tmp_path):
    """``aet docs lint`` fails the gate and reports the offending rule."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    (repo / "README.md").write_text("# Toolkit\n", encoding="utf-8")
    rules = repo / ".agents" / "doc-rules.yaml"
    rules.parent.mkdir(parents=True)
    rules.write_text(
        textwrap.dedent("""\
            rules:
              - type: must_contain
                target: README.md
                value: Governance
                reason: README must mention governance
            """),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(MAIN_PY), "docs", "lint"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout
    assert "README.md" in result.stderr
    assert "README must mention governance" in result.stderr


def test_make_validate_invokes_docs_lint():
    """The ``validate`` Makefile target includes the ``aet docs lint`` stage."""
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "aet.cli.main docs lint" in makefile


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

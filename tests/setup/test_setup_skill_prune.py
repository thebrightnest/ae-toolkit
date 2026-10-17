"""`aet setup skills` removes dangling toolkit skill links and nothing else.

When a skill is retired from the toolkit, its link in an agent skills dir is
left dangling. Other tools install skills there too, so pruning is limited to
links whose raw target is observed missing *and* sits in a toolkit ``skills/``
directory (ADR-059: absence is not a fact; only an observed missing target is).
All fixtures live under ``tmp_path``; the real ``~/.agents/skills`` is never touched.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

from tests.cli._helpers import run_typer

setup_mod = importlib.import_module("aet.cli.setup")


def _toolkit(root: Path, names: list[str]) -> Path:
    """Create a fake toolkit checkout holding ``src/aet/__init__.py`` and skills."""
    (root / "src" / "aet").mkdir(parents=True)
    (root / "src" / "aet" / "__init__.py").write_text("", encoding="utf-8")
    for name in names:
        d = root / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return root


@pytest.fixture
def fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    toolkit = _toolkit(tmp_path / "toolkit", ["aet-plan"])
    monkeypatch.setattr(setup_mod, "_repo_root", lambda: toolkit)
    target = tmp_path / "agent-skills"
    target.mkdir()

    # (a) dangling link into the toolkit's skills/ root
    (target / "aet-retired").symlink_to(toolkit / "skills" / "aet-retired")
    # (b) valid link into the same root
    (target / "aet-plan").symlink_to(toolkit / "skills" / "aet-plan")
    # (c) dangling foreign link
    (target / "foo").symlink_to(tmp_path / "other" / "skills" / "foo")
    # (d) real directory
    (target / "local-skill").mkdir()
    # (e) dangling link into a managed install whose skills/ dir is gone too
    managed = tmp_path / "ae-toolkit" / "repo"
    managed.mkdir(parents=True)
    (target / "aet-gone").symlink_to(managed / "skills" / "gone")

    return {"toolkit": toolkit, "target": target, "tmp": tmp_path}


def test_dangling_toolkit_link_is_a_toolkit_link(fixtures):
    assert setup_mod._is_toolkit_skill_link(fixtures["target"] / "aet-retired")


def test_valid_toolkit_link_is_a_toolkit_link(fixtures):
    assert setup_mod._is_toolkit_skill_link(fixtures["target"] / "aet-plan")


def test_foreign_link_is_not_a_toolkit_link(fixtures):
    assert not setup_mod._is_toolkit_skill_link(fixtures["target"] / "foo")


def test_real_directory_is_not_a_toolkit_link(fixtures):
    assert not setup_mod._is_toolkit_skill_link(fixtures["target"] / "local-skill")


def test_link_into_gone_managed_install_is_a_toolkit_link(fixtures):
    assert setup_mod._is_toolkit_skill_link(fixtures["target"] / "aet-gone")


def test_relative_symlink_target_is_resolved_against_link_parent(fixtures):
    link = fixtures["target"] / "aet-relative"
    rel = os.path.relpath(fixtures["toolkit"] / "skills" / "aet-relative", fixtures["target"])
    link.symlink_to(rel)

    assert setup_mod._is_toolkit_skill_link(link)


def test_link_into_toolkit_root_not_named_skills_is_not_a_toolkit_link(fixtures):
    link = fixtures["target"] / "aet-docs"
    link.symlink_to(fixtures["toolkit"] / "docs" / "aet-docs")

    assert not setup_mod._is_toolkit_skill_link(link)


def test_link_into_toolkit_found_by_package_marker(tmp_path, monkeypatch):
    """A second checkout (not ``_repo_root()``) is still identified as toolkit."""
    other = _toolkit(tmp_path / "other-checkout", [])
    monkeypatch.setattr(setup_mod, "_repo_root", lambda: tmp_path / "elsewhere")
    link = tmp_path / "x"
    link.symlink_to(other / "skills" / "x")

    assert setup_mod._is_toolkit_skill_link(link)


def test_dangling_scan_returns_only_dangling_toolkit_links_sorted(fixtures):
    found = setup_mod._dangling_toolkit_skill_links(fixtures["target"])

    assert [p.name for p in found] == ["aet-gone", "aet-retired"]


def test_setup_skills_removes_only_dangling_toolkit_links(fixtures):
    target = fixtures["target"]

    result = run_typer(
        setup_mod.app,
        ["skills", "--skills-dir", str(target)],
        env={"AET_REPO_ROOT": str(fixtures["toolkit"])},
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    assert not os.path.lexists(target / "aet-retired")
    assert not os.path.lexists(target / "aet-gone")
    assert (target / "aet-plan").is_symlink() and (target / "aet-plan").exists()
    assert (target / "foo").is_symlink()
    assert (target / "local-skill").is_dir()
    assert "removed dangling skill link aet-retired ->" in result.stdout
    assert "removed dangling skill link aet-gone ->" in result.stdout
    assert "pruned 2 dangling skill link(s)" in result.stdout

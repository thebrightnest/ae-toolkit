"""Tests for the validate gate's change-scope decision.

The gate skips pytest entirely when a change is prose-only. That is only safe
while no test module reads the repo's own Markdown, so the regression guard
below fails whenever a module starts doing so.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from aet import change_scope, telemetry, test_deps

REPO_ROOT = Path(__file__).resolve().parents[1]
_REHEARSAL = "tests/orchestrator/test_single_pr_rehearsal.py"
TESTS_DIR = REPO_ROOT / "tests"


def _eval_path(node: ast.AST, anchors: dict[str, Path], file_path: Path):
    """Statically evaluate a pathlib expression to an absolute path.

    Returns a :class:`Path` for a resolvable expression, a ``str`` for a bare
    literal segment (so ``/`` joins can consume it), or ``None`` when the
    expression depends on anything not knowable from the source.
    """
    if isinstance(node, ast.Name):
        return anchors.get(node.id)
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "Path":
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Name) and first.id == "__file__":
                return file_path
            return None
        if isinstance(func, ast.Attribute) and func.attr == "resolve":
            return _eval_path(func.value, anchors, file_path)
        return None
    if isinstance(node, ast.Subscript):
        value = node.value
        if isinstance(value, ast.Attribute) and value.attr == "parents":
            base = _eval_path(value.value, anchors, file_path)
            index = node.slice
            if isinstance(base, Path) and isinstance(index, ast.Constant):
                try:
                    return base.parents[index.value]
                except (IndexError, TypeError):
                    return None
        return None
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        base = _eval_path(node.value, anchors, file_path)
        return base.parent if isinstance(base, Path) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _eval_path(node.left, anchors, file_path)
        right = _eval_path(node.right, anchors, file_path)
        if isinstance(left, Path) and isinstance(right, str):
            return left / right
        return None
    return None


def _anchors_for(tree: ast.Module, file_path: Path) -> dict[str, Path]:
    """Module constants that resolve to a real location in this checkout."""
    anchors: dict[str, Path] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        resolved = _eval_path(node.value, anchors, file_path)
        if not isinstance(resolved, Path):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                anchors[target.id] = resolved
    return anchors


def _is_repo_prose(path: Path) -> bool:
    """A Markdown path in the checkout that change_scope would call prose."""
    if TESTS_DIR in path.parents:
        return False
    return not change_scope.is_code_path(str(path.relative_to(REPO_ROOT)))


def _reads_repo_markdown(path: Path) -> bool:
    """Whether this module reads Markdown from the checkout itself.

    Resolves path expressions rather than pattern-matching them, so temp-repo
    fixtures that merely *mention* ``docs/plans/x.md`` are not mistaken for
    reads of the real corpus.
    """
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover - a broken test file fails elsewhere
        return False
    anchors = _anchors_for(tree, path)
    if not anchors:
        return False

    for node in ast.walk(tree):
        # A direct join: REPO_ROOT / "docs" / "CONVENTIONS.md"
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            resolved = _eval_path(node, anchors, path)
            if (
                isinstance(resolved, Path)
                and resolved.suffix == ".md"
                and _is_repo_prose(resolved)
            ):
                return True
        # A glob over a repo directory: plans_dir.glob("*.md")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr not in ("glob", "rglob"):
                continue
            pattern = node.args[0] if node.args else None
            if not (isinstance(pattern, ast.Constant) and str(pattern.value).endswith(".md")):
                continue
            directory = _eval_path(node.func.value, anchors, path)
            if isinstance(directory, Path) and _is_repo_prose(directory / "probe.md"):
                return True
    return False


# Tests that intentionally read repo Markdown as their validation target.
# They must still run on prose-only changes, so they are not a silent
# under-test risk.
_EXEMPT_READERS = {
    "tests/cli/test_retired_names.py",
    "tests/cli/test_docs_generate.py",
}


class TestNoRepoMarkdownReaders:
    """Prose-only changes skip pytest, so tests must not read repo Markdown."""

    def test_no_module_under_tests_reads_repo_markdown(self):
        readers = {
            str(p.relative_to(REPO_ROOT))
            for p in TESTS_DIR.rglob("test_*.py")
            if _reads_repo_markdown(p)
        } - _EXEMPT_READERS
        assert not readers, (
            "These test modules read the repo's Markdown outside tests/: "
            f"{sorted(readers)}. A prose-only change skips pytest, so any "
            "such coupling reintroduces a silent under-test risk."
        )


class TestIsCodePath:
    """Prose is narrow; everything else forces a full run."""

    def test_markdown_outside_tests_is_prose(self):
        assert not change_scope.is_code_path("README.md")
        assert not change_scope.is_code_path("docs/plans/abc-01.md")
        assert not change_scope.is_code_path("aet-ship/SKILL.md")

    def test_markdown_fixtures_under_tests_are_code(self):
        """The stricter rule this module adds over evidence.default_is_code_path."""
        assert change_scope.is_code_path("tests/fixtures/skills-lint/legacy.md")
        assert change_scope.is_code_path("tests/orchestrator/test_orchestrator.py")

    def test_executables_and_config_are_code(self):
        for path in (
            "src/aet/queue.py",
            "scripts/skills-lint",
            "scripts/hooks/pre-push",
            "Makefile",
            "pyproject.toml",
            "src/aet/workflows/default.json",
        ):
            assert change_scope.is_code_path(path), path

    def test_unknown_and_empty_paths_are_code(self):
        assert change_scope.is_code_path("")
        assert change_scope.is_code_path("some/unrecognized/binary")


class TestDecide:
    """The decision is fail-safe: only a known, all-prose change set skips pytest."""

    def test_all_prose_decides_docs(self):
        assert change_scope.decide(["README.md", "docs/plans/x.md"]) == change_scope.DOCS

    def test_one_code_path_forces_full(self):
        paths = ["README.md", "docs/plans/x.md", "src/aet/queue.py"]
        assert change_scope.decide(paths) == change_scope.FULL

    def test_undetermined_change_set_forces_full(self):
        assert change_scope.decide(None) == change_scope.FULL

    def test_empty_change_set_forces_full(self):
        assert change_scope.decide([]) == change_scope.FULL


class TestTargetsAndTier:
    """Targeted validation scope derived from the change set, never the plan stage."""

    def test_change_scope_selects_only_tests_that_reach_the_change(self):
        selected = change_scope.targets(["src/aet/identity.py"])
        assert "tests/test_identity.py" in selected
        assert all(Path(REPO_ROOT / t).exists() for t in selected), selected

    def test_change_scope_falls_back_to_full_suite_on_conftest_or_shared_fixture(self):
        assert change_scope.targets(["tests/conftest.py"]) == ["tests/"]
        assert change_scope.targets(["tests/fixtures/skills-lint/legacy.md"]) == ["tests/"]

    def test_change_scope_emits_installer_target_only_when_installer_surface_changed(self):
        """ADR-049 §2. The setup.py edge crosses a shell boundary the source
        cannot show, so it is declared in ``test_deps.BOUNDARY_EDGES``."""
        deps = test_deps.dependency_map(str(REPO_ROOT))
        installer = "tests/installer/test_installer.py"

        assert installer in change_scope.targets(["scripts/install.sh"])
        assert installer in deps.tests_for("src/aet/cli/setup.py")
        assert installer not in deps.tests_for("src/aet/identity.py")
        assert installer not in change_scope.targets(["src/aet/identity.py"])

    def test_change_scope_never_names_a_path_pytest_cannot_collect(self):
        """A phantom target makes pytest exit 4 and runs nothing.

        The filename-derived mechanism this replaced appended its floor
        unmapped-or-not, naming a non-existent file for 69 of 82 modules.
        """
        for module in test_deps.dependency_map(str(REPO_ROOT)).modules:
            for target in change_scope.targets([module]):
                assert (REPO_ROOT / target).exists(), f"{module} -> {target}"

    def test_change_scope_omits_installer_target_for_unrelated_change(self):
        assert "tests/installer/test_installer.py" not in change_scope.targets(
            ["src/aet/queue.py"]
        )

    def test_change_scope_tier_reuses_evidence_vocabulary_and_ignores_stage(self):
        from aet import evidence

        assert change_scope.tier(["src/aet/queue.py"]) == evidence.RUN
        assert change_scope.tier(["README.md"]) == evidence.LINT_ONLY
        assert change_scope.tier(None) == evidence.RUN
        assert change_scope.tier([]) == evidence.RUN
        # The tier is a pure function of paths; no stage argument exists.
        import inspect

        sig = inspect.signature(change_scope.tier)
        assert "stage" not in sig.parameters

    @pytest.mark.parametrize(
        "path",
        [
            "src/aet/cli/orchestrator.py",
            "src/aet/integration_lock.py",
            "src/aet/worktree.py",
            "src/aet/backends/factory.py",
        ],
    )
    def test_single_pr_rehearsal_covers_the_integration_surface(self, path):
        """ADR-049's rehearsal trigger, now a property rather than a list.

        The four prefixes were named explicitly because a table cannot know
        what a test exercises. The rehearsal reaches all four through the
        import graph, so the trigger needs no separate declaration — and this
        fails if the rehearsal ever stops covering one of them. Asserted on the
        derivation rather than on ``targets``, which collapses a hub module's
        selection to the whole suite.
        """
        deps = test_deps.dependency_map(str(REPO_ROOT))
        assert _REHEARSAL in deps.tests_for(path)

    def test_selection_narrows_to_the_change(self):
        assert _REHEARSAL not in change_scope.targets(["src/aet/identity.py"])

    def test_shared_fixture_in_the_change_set_forces_the_full_suite(self):
        targets = change_scope.targets(["src/aet/integration_lock.py", "tests/conftest.py"])
        assert targets == ["tests/"]

    def test_a_path_no_test_reaches_forces_the_full_suite(self):
        targets = change_scope.targets(
            ["src/aet/integration_lock.py", "some/unrecognized/binary"]
        )
        assert targets == ["tests/"]

    def test_root_config_changes_force_the_full_suite(self):
        for path in ("pyproject.toml", "Makefile"):
            assert change_scope.targets([path]) == ["tests/"], path

    def test_a_hub_module_collapses_to_the_full_suite(self):
        """Naming most of the suite one file at a time is the same run, spelled long."""
        assert change_scope.targets(["src/aet/plan_parser.py"]) == ["tests/"]


class TestResolvedTargetsMarker:
    """``--explain`` carries a machine-readable marker beside its human line.

    The human line is for operators and may be re-worded freely; the marker is
    the contract `telemetry.classify_test_scope` reads (tap-06).
    """

    def _explain(self, monkeypatch, capsys, paths):
        monkeypatch.setattr(change_scope, "changed_paths", lambda: paths)
        change_scope.main(["--explain"])
        return capsys.readouterr().out

    def test_change_scope_emits_resolved_targets_marker(self, monkeypatch, capsys):
        selected = " ".join(change_scope.targets(["src/aet/identity.py"]))
        out = self._explain(monkeypatch, capsys, ["src/aet/identity.py"])

        assert f"{telemetry.TEST_SCOPE_MARKER_PREFIX} {selected}" in out
        # The operator-facing line survives alongside it.
        assert f"→ targeted tests: {selected}" in out

    def test_marker_absent_for_prose_only_change(self, monkeypatch, capsys):
        out = self._explain(monkeypatch, capsys, ["README.md"])
        assert telemetry.TEST_SCOPE_MARKER_PREFIX not in out

    def test_marker_never_reaches_the_bare_target_list(self, monkeypatch, capsys):
        """Without ``--explain`` the output *is* ``PYTEST_TARGETS``, marker-free.

        The Makefile interpolates this stdout straight into the pytest target
        list. A marker line leaking out of the ``--explain`` branch would make
        pytest run against a non-existent path, so the separation is pinned
        rather than left to the reader of ``main``.
        """
        monkeypatch.setattr(
            change_scope, "changed_paths", lambda: ["src/aet/identity.py"]
        )
        expected = " ".join(change_scope.targets(["src/aet/identity.py"]))
        change_scope.main([])
        assert capsys.readouterr().out == f"{expected}\n"


# The acknowledged-uncovered list is data, not code: a path named in a Python
# test file would read as coverage of that path to the deriver under test, and
# the list would make itself true.
_UNCOVERED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "uncovered-source-files.txt"


def _acknowledged_uncovered() -> set[str]:
    """Source files recorded as reached by no test."""
    lines = _UNCOVERED_FIXTURE.read_text(encoding="utf-8").splitlines()
    return {
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    }


def _uncovered_source_files() -> set[str]:
    """Every source file that no test file reaches."""
    deps = test_deps.dependency_map(str(REPO_ROOT))
    return {path for path in deps.modules if not deps.tests_for(path)}


class TestCoverageDerivationDrift:
    """Selection is derived, but "nothing reaches this" still needs a guard."""

    def test_every_source_file_is_reached_by_some_test(self):
        new = _uncovered_source_files() - _acknowledged_uncovered()
        assert not new, (
            f"No test reaches these source files: {sorted(new)}. Add a test "
            "that imports the module (or names the script), or add them to "
            "tests/fixtures/uncovered-source-files.txt with a reason if the full suite really is the right "
            "target."
        )

    def test_the_uncovered_list_has_no_stale_entries(self):
        stale = _acknowledged_uncovered() - _uncovered_source_files()
        assert not stale, (
            f"These source files are reached by tests now but still listed as "
            f"uncovered: {sorted(stale)}. Remove them from tests/fixtures/uncovered-source-files.txt."
        )

    def test_boundary_edges_name_real_files(self):
        """A declared edge that names a moved file would silently stop working."""
        deps = test_deps.dependency_map(str(REPO_ROOT))
        known_tests = set(deps.test_files)
        known_sources = set(deps.modules)
        for source, tests in test_deps.BOUNDARY_EDGES.items():
            assert source in known_sources, source
            for test in tests:
                assert test in known_tests, test

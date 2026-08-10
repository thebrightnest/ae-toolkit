"""Tests for the validate gate's change-scope decision.

The gate skips pytest entirely when a change is prose-only. That is only safe
while no test module reads the repo's own Markdown, so the regression guard
below fails whenever a module starts doing so.
"""

from __future__ import annotations

import ast
from pathlib import Path

from aet import change_scope, telemetry

REPO_ROOT = Path(__file__).resolve().parents[1]
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

    def test_change_scope_maps_source_dir_to_targeted_test_dir(self):
        assert change_scope.targets(["src/aet/queue.py"]) == ["tests/queue"]

    def test_change_scope_falls_back_to_full_suite_on_conftest_or_shared_fixture(self):
        assert change_scope.targets(["tests/conftest.py"]) == ["tests/"]
        assert change_scope.targets(["tests/fixtures/skills-lint/legacy.md"]) == ["tests/"]

    def test_change_scope_emits_installer_target_only_when_installer_surface_changed(self):
        assert change_scope.targets(["scripts/install.sh"]) == [
            "tests/installer/test_installer.py"
        ]
        assert change_scope.targets(["src/aet/cli/setup.py"]) == [
            "tests/installer/test_installer.py"
        ]

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
        out = self._explain(monkeypatch, capsys, ["src/aet/queue.py"])
        assert f"{telemetry.TEST_SCOPE_MARKER_PREFIX} tests/queue" in out
        # The operator-facing line survives alongside it.
        assert "→ targeted tests: tests/queue" in out

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
        monkeypatch.setattr(change_scope, "changed_paths", lambda: ["src/aet/queue.py"])
        change_scope.main([])
        assert capsys.readouterr().out == "tests/queue\n"

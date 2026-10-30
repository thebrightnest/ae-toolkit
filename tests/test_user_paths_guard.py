"""Guard tests for user-level paths isolation.

Ensures that:
1. No module in src/aet/ outside user_paths.py constructs paths under ~/.aet/.
2. Every resolver points into the isolated test home directory during tests.
"""

from __future__ import annotations

import ast
from pathlib import Path

from aet import evidence, telemetry, user_paths


class AetHomeVisitor(ast.NodeVisitor):
    """AST visitor that detects constructs building paths under ~/.aet/."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Div):
            if self._is_home_expr(node.left) and self._is_aet_str(node.right):
                self.violations.append(
                    f"Line {node.lineno}: Path.home() / '.aet' pattern"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name == "expanduser":
            if node.args and isinstance(node.args[0], ast.Constant):
                val = str(node.args[0].value)
                if "~/.aet" in val or val == "~/.aet":
                    self.violations.append(
                        f"Line {node.lineno}: expanduser with ~/.aet pattern: {val!r}"
                    )
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Call):
                inner = node.func.value
                if isinstance(inner.func, ast.Name) and inner.func.id == "Path":
                    if inner.args and isinstance(inner.args[0], ast.Constant):
                        val = str(inner.args[0].value)
                        if "~/.aet" in val:
                            self.violations.append(
                                f"Line {node.lineno}: Path('~/.aet').expanduser() pattern"
                            )

        if func_name == "join":
            has_home = any(self._is_home_expr(a) for a in node.args)
            has_aet = any(self._is_aet_str(a) for a in node.args)
            if has_home and has_aet:
                self.violations.append(
                    f"Line {node.lineno}: join with home and '.aet'"
                )

        self.generic_visit(node)

    def _is_home_expr(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "home":
                return True
            if (
                (isinstance(node.func, ast.Name) and node.func.id == "expanduser")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "expanduser")
            ):
                if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "~":
                    return True
        return False

    def _is_aet_str(self, node: ast.AST) -> bool:
        return isinstance(node, ast.Constant) and node.value in (".aet", "/.aet")


def scan_source_for_aet_home(source: str) -> list[str]:
    """Parse python source and report any constructs building ~/.aet/ paths."""
    tree = ast.parse(source)
    visitor = AetHomeVisitor()
    visitor.visit(tree)
    return visitor.violations


def test_no_aet_home_path_outside_resolver(tmp_path):
    """Scan src/aet/ for ~/.aet paths outside user_paths.py, and verify plant detection."""
    # 1. Verify that a planted Path.home() / ".aet" in a temporary module fails with module name
    fake_module = tmp_path / "planted_leak.py"
    fake_module.write_text('bad_path = Path.home() / ".aet" / "oops"\n', encoding="utf-8")
    violations = scan_source_for_aet_home(fake_module.read_text(encoding="utf-8"))
    assert violations, f"Expected violations in planted module {fake_module.name}"

    # 2. Scan all python files in src/aet/ except user_paths.py
    repo_src = Path(__file__).parent.parent / "src" / "aet"
    found_violations: dict[str, list[str]] = {}
    for py_file in sorted(repo_src.rglob("*.py")):
        if py_file.name == "user_paths.py":
            continue
        v = scan_source_for_aet_home(py_file.read_text(encoding="utf-8"))
        if v:
            module_name = py_file.relative_to(repo_src).as_posix()
            found_violations[module_name] = v

    assert not found_violations, (
        f"Found ~/.aet home path outside user_paths.py in modules: {found_violations}"
    )


def test_resolvers_point_into_test_home():
    """Verify that every resolver returns a path within the isolated test home."""
    real_home_aet = Path.home() / ".aet"
    test_home = user_paths.aet_home()

    resolvers = [
        ("aet_home", user_paths.aet_home()),
        ("telemetry_archive_dir", user_paths.telemetry_archive_dir()),
        ("reports_dir", user_paths.reports_dir()),
        ("user_config_path", user_paths.user_config_path("test-slug")),
        ("telemetry.archive_dir", telemetry.archive_dir()),
        ("evidence.reports_dir", evidence.reports_dir()),
    ]

    for name, resolved_path in resolvers:
        assert not resolved_path.is_relative_to(real_home_aet), (
            f"Resolver {name!r} returned path under real ~/.aet: {resolved_path}"
        )
        assert resolved_path.is_relative_to(test_home), (
            f"Resolver {name!r} did not return path under test home ({test_home}): {resolved_path}"
        )

"""Register and regression guard for tolerated known intermittent test failures (R-7).

Every xfail marker in tests/ must be registered here with its reason and
the report that records it, so the set is enumerable and a marker cannot
outlive its reason unnoticed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"


@dataclass(frozen=True)
class ToleratedRed:
    file: str
    target: str
    reason: str
    report: str

    @property
    def citation(self) -> str:
        return f"{self.reason}; {self.report}"


_SERIALIZATION_KEY = (
    "tests/orchestrator/test_integration_serialization.py::test_max_jobs_three_integration_steps_serialize"
)

TOLERATED_REDS: dict[str, ToleratedRed] = {
    _SERIALIZATION_KEY: ToleratedRed(
        file="tests/orchestrator/test_integration_serialization.py",
        target="test_max_jobs_three_integration_steps_serialize",
        reason="fails under --dist=loadgroup, passes in isolation (cause not established since 2026-07-24)",
        report="content/backlog/debt-gate-tolerates-known-intermittent-reds.md",
    ),
    "tests/orchestrator/test_nightshift_rehearsal.py::test_stall_killed_and_classified_timeout": ToleratedRed(
        file="tests/orchestrator/test_nightshift_rehearsal.py",
        target="test_stall_killed_and_classified_timeout",
        reason="13–27% flake across 30 runs in August 2026; unreproducible",
        report="docs/bugs/20260824-nightshift-stall-timeout-flake.md",
    ),
    "tests/test_aet_run_dispatch.py::test_run_one_blocks_until_terminal_state_and_returns_rc": ToleratedRed(
        file="tests/test_aet_run_dispatch.py",
        target="test_run_one_blocks_until_terminal_state_and_returns_rc",
        reason="seen once under -n auto (not investigated)",
        report="content/backlog/debt-gate-tolerates-known-intermittent-reds.md",
    ),
}


def _is_xfail_decorator(decorator: ast.AST) -> tuple[bool, bool | None, str | None]:
    """Check if an AST decorator node is pytest.mark.xfail and extract strict/reason."""
    func_node = decorator
    args = []
    keywords = {}
    if isinstance(decorator, ast.Call):
        func_node = decorator.func
        args = decorator.args
        keywords = {kw.arg: kw.value for kw in decorator.keywords if kw.arg}

    # Match pytest.mark.xfail
    is_xfail = False
    if isinstance(func_node, ast.Attribute) and func_node.attr == "xfail":
        val = func_node.value
        if isinstance(val, ast.Attribute) and val.attr == "mark":
            if isinstance(val.value, ast.Name) and val.value.id == "pytest":
                is_xfail = True

    if not is_xfail:
        return False, None, None

    strict_val = None
    if "strict" in keywords:
        kw = keywords["strict"]
        if isinstance(kw, ast.Constant):
            strict_val = kw.value

    reason_val = None
    if "reason" in keywords:
        kw = keywords["reason"]
        if isinstance(kw, ast.Constant) and isinstance(kw.value, str):
            reason_val = kw.value
        elif isinstance(kw, ast.JoinedStr):
            # Joined string (f-string or multi-part string literal)
            parts = []
            for part in kw.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    parts.append(part.value)
            reason_val = "".join(parts)
        elif isinstance(kw, ast.BinOp) and isinstance(kw.op, ast.Add):
            # String concatenation
            reason_val = ast.unparse(kw)
    elif args and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
        reason_val = args[0].value

    return True, strict_val, reason_val


def discover_xfail_markers() -> dict[str, dict]:
    """Scan tests/ for all @pytest.mark.xfail markers."""
    markers: dict[str, dict] = {}
    for test_file in sorted(list(TESTS_DIR.rglob("*.py"))):
        rel_path = test_file.relative_to(REPO_ROOT).as_posix()
        if rel_path == "tests/test_tolerated_reds.py":
            continue
        try:
            tree = ast.parse(test_file.read_text(encoding="utf-8"), filename=str(test_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for dec in node.decorator_list:
                    matched, strict, reason = _is_xfail_decorator(dec)
                    if matched:
                        key = f"{rel_path}::{node.name}"
                        markers[key] = {
                            "file": rel_path,
                            "target": node.name,
                            "strict": strict,
                            "reason": reason,
                            "node": node,
                        }
    return markers


def test_tolerated_reds_register_matches_markers():
    """Every xfail marker in tests/ must be in TOLERATED_REDS, and vice-versa."""
    discovered = discover_xfail_markers()
    discovered_keys = set(discovered.keys())
    registered_keys = set(TOLERATED_REDS.keys())

    missing_from_register = discovered_keys - registered_keys
    missing_from_code = registered_keys - discovered_keys

    assert not missing_from_register, (
        f"Found xfail markers not in TOLERATED_REDS register: {sorted(missing_from_register)}. "
        "Every tolerated red must be registered in tests/test_tolerated_reds.py."
    )
    assert not missing_from_code, (
        f"TOLERATED_REDS registers entries without corresponding xfail markers in code: {sorted(missing_from_code)}. "
        "A marker cannot be removed from code without updating the register."
    )


def test_all_tolerated_markers_are_non_strict():
    """All tolerated red markers must be xfail(strict=False) so unexpected passes still report."""
    discovered = discover_xfail_markers()
    for key, info in discovered.items():
        assert info["strict"] is False, (
            f"{key}: expected xfail(strict=False), got strict={info['strict']!r}"
        )


def test_all_tolerated_markers_cite_report():
    """All tolerated red markers must specify a reason citing their tracking report."""
    discovered = discover_xfail_markers()
    for key, info in discovered.items():
        registered = TOLERATED_REDS.get(key)
        assert registered is not None, f"Unregistered marker {key}"
        assert info["reason"] is not None and len(info["reason"].strip()) > 0, (
            f"{key}: xfail marker must include a reason"
        )
        assert registered.report in (info["reason"] or "") or registered.reason in (info["reason"] or ""), (
            f"{key}: xfail reason ({info['reason']!r}) does not cite report or reason from register"
        )


def test_registered_target_files_exist():
    """Every file in TOLERATED_REDS must exist in the repository."""
    for key, registered in TOLERATED_REDS.items():
        target_file = REPO_ROOT / registered.file
        assert target_file.exists(), f"{key}: registered file {registered.file} does not exist"


def test_orchestrator_log_in_retired_ignored_paths():
    """scripts/.aet-work-orchestrator.log must be registered in AET_RETIRED_IGNORED_PATHS."""
    from aet.worktree import AET_RETIRED_IGNORED_PATHS

    assert "scripts/.aet-work-orchestrator.log" in AET_RETIRED_IGNORED_PATHS


def test_removed_dead_artifacts_not_present():
    """Obsolete test-merge-verified-removed.sh and .aet-work-orchestrator.log are deleted."""
    assert not (REPO_ROOT / "scripts/test-merge-verified-removed.sh").exists()
    assert not (REPO_ROOT / "scripts/.aet-work-orchestrator.log").exists()


def test_removed_script_not_in_uncovered_fixtures():
    """scripts/test-merge-verified-removed.sh must not be in uncovered-source-files.txt."""
    uncovered = (REPO_ROOT / "tests/fixtures/uncovered-source-files.txt").read_text(encoding="utf-8")
    assert "scripts/test-merge-verified-removed.sh" not in uncovered

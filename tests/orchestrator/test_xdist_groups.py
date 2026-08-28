"""Regression guard for the orchestrator xdist subgroup taxonomy (vre-02).

Every file that used to carry the monolithic ``xdist_group("orchestrator")``
marker must now carry a resource-scoped subgroup marker. The three tests that
were proven to conflict when the monolith was dropped stay co-grouped with the
rest of the process-group tests they race against.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parents[2]

# Resource-scoped subgroups keyed on the mutable resource each test contends for.
# See docs/CONVENTIONS.md "Test parallelization" for the rationale.
EXPECTED_SUBGROUPS: dict[str, list[str]] = {
    "process-group": [
        # Real orchestrator subprocesses and process-group lifecycle.
        "tests/orchestrator/test_orchestrator.py",
        "tests/orchestrator/test_stall_watchdog.py",
        "tests/orchestrator/test_nightshift_rehearsal.py",
    ],
    "cwd": [
        # Mutates the process-wide working directory.
        "tests/backends/test_git_refs_backend.py",
    ],
    "telemetry-dir": [
        # Exercises telemetry archive paths / orchestrator state without heavy
        # subprocesses or git mutation.
        "tests/orchestrator/test_orchestrator_derived.py",
        "tests/orchestrator/test_status_liveness_contract.py",
        "tests/orchestrator/test_read_path_no_git.py",
    ],
    "git-repo": [
        # Initializes and manipulates temporary git repositories.
        "tests/gate/test_integration_gate_evidence.py",
        "tests/orchestrator/test_pr_per_task_unchanged.py",
        "tests/orchestrator/test_single_pr_loop.py",
        "tests/orchestrator/test_integration_push.py",
        "tests/orchestrator/test_circuit_breaker.py",
        "tests/orchestrator/test_on_failure_triage.py",
        "tests/orchestrator/test_integration_serialization.py",
        "tests/orchestrator/test_missing_plan_halts.py",
        "tests/orchestrator/test_task_record_replication.py",
        "tests/orchestrator/test_stage_credit_on_failure.py",
    ],
}

# Flatten to the file-level mapping expected by the test assertions.
EXPECTED_FILE_GROUPS: dict[str, str] = {
    file_path: group for group, file_paths in EXPECTED_SUBGROUPS.items() for file_path in file_paths
}


def _read_pytestmark(file_path: str) -> str | None:
    """Return the literal xdist_group argument string, or None if absent."""
    text = (_REPO_ROOT / file_path).read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("pytestmark = pytest.mark.xdist_group("):
            # Extract the quoted argument.
            arg = line.split("(", 1)[1].rsplit(")", 1)[0].strip().strip('"')
            return arg
    return None


@pytest.mark.parametrize("file_path,expected_group", EXPECTED_FILE_GROUPS.items())
def test_orchestrator_file_belongs_to_expected_subgroup(file_path: str, expected_group: str) -> None:
    """Each legacy orchestrator xdist file now uses the correct resource-scoped subgroup."""
    actual = _read_pytestmark(file_path)
    assert actual == expected_group, f"{file_path}: expected {expected_group!r}, got {actual!r}"


def test_no_orchestrator_file_uses_legacy_monolith_group() -> None:
    """The old monolithic 'orchestrator' group is gone from the 15 legacy sites."""
    for file_path in EXPECTED_FILE_GROUPS:
        actual = _read_pytestmark(file_path)
        assert actual != "orchestrator", f"{file_path} still uses legacy 'orchestrator' group"


def test_conflict_floor_tests_remain_in_process_group() -> None:
    """The three proven-conflicting tests stay in the process-group cohort."""
    text = (_REPO_ROOT / "tests/orchestrator/test_orchestrator.py").read_text(encoding="utf-8")
    assert 'pytestmark = pytest.mark.xdist_group("process-group")' in text
    conflict_floor = {
        "test_batch_spawns_task_promoted_mid_run",
        "test_emit_stage_session_classifies_failure_for_nonzero_exit",
        "test_cleanup_kills_process_groups_on_shutdown",
    }
    for name in conflict_floor:
        assert f"def {name}(" in text, f"conflict-floor test {name} not found in test_orchestrator.py"

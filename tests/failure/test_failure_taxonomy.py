"""Tests for the failure taxonomy classifier and normalized signature."""

import pytest

from aet.failure import FailureClass, classify, signature


def test_classify_shutdown_is_canceled():
    """A shutdown request always wins over every other signal."""
    assert (
        classify(
            exit_code=1,
            tail="AssertionError: expected 1 == 2\n",
            stage="verify",
            verdict_recorded=True,
            shutdown=True,
            killed_by_timeout=False,
        )
        == FailureClass.CANCELED
    )


def test_classify_killed_by_timeout_is_timeout():
    """A watchdog kill is classified as a timeout."""
    assert (
        classify(
            exit_code=137,
            tail="Killed\n",
            stage="run",
            verdict_recorded=False,
            shutdown=False,
            killed_by_timeout=True,
        )
        == FailureClass.TIMEOUT
    )


@pytest.mark.parametrize(
    ("tail", "verdict_recorded", "expected"),
    [
        ("ModuleNotFoundError: No module named 'requests'\n", False, FailureClass.ENVIRONMENT),
        ("Connection refused: api.example.com:443\n", False, FailureClass.ENVIRONMENT),
        ("Authentication failed for user deployer\n", False, FailureClass.ENVIRONMENT),
        ("FAILED test_verify.py::test_gate - AssertionError: 1 != 2\n", True, FailureClass.DESIGN),
        ("assertion failed: expected value to be true\n", True, FailureClass.DESIGN),
        ("TypeError: unsupported operand type(s)\n", True, FailureClass.DESIGN),
        ("some incidental output\n", False, FailureClass.FLAKY),
    ],
)
def test_classify_each_category(tail, verdict_recorded, expected):
    """Tail patterns partition environment, design, and flaky failures."""
    assert (
        classify(
            exit_code=1,
            tail=tail,
            stage="run",
            verdict_recorded=verdict_recorded,
            shutdown=False,
            killed_by_timeout=False,
        )
        == expected
    )


def test_classify_ambiguous_defaults_environment():
    """When the tail has no stable class signal, default to environment."""
    assert (
        classify(
            exit_code=0,
            tail="something went wrong\n",
            stage="run",
            verdict_recorded=False,
            shutdown=False,
            killed_by_timeout=False,
        )
        == FailureClass.ENVIRONMENT
    )


@pytest.mark.parametrize(
    ("tail", "verdict_recorded", "expected"),
    [
        # Bare "missing" / "not found" / "dependency" in a design-failure tail
        # must not drag the class to environment.
        (
            "FAILED test_api.py::test_create - AssertionError: field missing from response\n",
            True,
            FailureClass.DESIGN,
        ),
        (
            "FAILED test_gate.py::test_x - fixture 'db' not found\n",
            True,
            FailureClass.DESIGN,
        ),
        (
            "TypeError: dependency injection container mismatch\n",
            True,
            FailureClass.DESIGN,
        ),
        # Without a recorded verdict, the same tails are flaky, not environment.
        ("AssertionError: field missing from response\n", False, FailureClass.FLAKY),
        # Qualified environment signals still classify as environment.
        ("pip failed: missing dependency 'libssl'\n", False, FailureClass.ENVIRONMENT),
        ("sh: aet-state: command not found\n", False, FailureClass.ENVIRONMENT),
        ("ld: cannot find module 'ssl'\n", False, FailureClass.ENVIRONMENT),
        # Bare "cannot find" in a design tail is not an environment signal.
        (
            "FAILED test_plan.py::test_x - cannot find a matching task in the queue\n",
            True,
            FailureClass.DESIGN,
        ),
    ],
)
def test_classify_narrowed_environment_patterns(tail, verdict_recorded, expected):
    """Qualified environment signals match; bare words in design tails do not."""
    assert (
        classify(
            exit_code=1,
            tail=tail,
            stage="run",
            verdict_recorded=verdict_recorded,
            shutdown=False,
            killed_by_timeout=False,
        )
        == expected
    )


def test_signature_stable_across_volatile_spans():
    """Volatile spans (paths, PIDs, timestamps, line numbers) do not change the signature."""
    base_error = "AssertionError: expected 2 but got 1"
    tail_a = (
        "[2024-01-15T09:23:17Z] pid 12345 /home/user/proj/test_run.py:42:13\n"
        f"{base_error}\n"
    )
    tail_b = (
        "[2026-07-16T23:09:22Z] pid 99999 ./rel/path/test_run.py:99:7\n"
        f"{base_error}\n"
    )
    assert signature(stage="verify", tail=tail_a) == signature(stage="verify", tail=tail_b)


def test_signature_distinct_across_stage_and_error_class():
    """Different stages or error classes produce different signatures."""
    tail = "AssertionError: expected 2 but got 1\n"
    sig_a = signature(stage="verify", tail=tail)
    sig_b = signature(stage="run", tail=tail)
    sig_c = signature(stage="verify", tail="TypeError: bad operand\n")
    assert sig_a != sig_b
    assert sig_a != sig_c

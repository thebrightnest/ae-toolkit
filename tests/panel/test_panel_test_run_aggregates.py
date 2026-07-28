"""Tests for the panel's provenance-split test_run aggregates (ADR-051, R-8).

The aggregate logic lives in ``src/aet/panel/index.html``. These tests extract
the marked helper block verbatim and execute it under node, so the assertions
run against the code the browser runs rather than a Python restatement of it.
Node is already a build dependency of this repo (``make lint`` / ``make
format``), so its absence is a failure, not a skip.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

PANEL_HTML = Path(__file__).parents[2] / "src" / "aet" / "panel" / "index.html"
MARK_START = "// PROVENANCE-HELPERS-START"
MARK_END = "// PROVENANCE-HELPERS-END"

OBSERVED = {
    "type": "test_run",
    "source": "wire",
    "scope": "full-suite",
    "test_command": "pytest tests/",
    "duration_seconds": 40.0,
    "exit_code": 0,
    "result": "success",
    "tests_total": None,
    "tests_passed": None,
    "tests_failed": None,
}
CLAIMED = {
    "type": "test_run",
    "source": "verdict",
    "scope": "full-suite",
    "test_command": "pytest tests/",
    "duration_seconds": None,
    "exit_code": None,
    "result": "unknown",
    "tests_total": 100,
    "tests_passed": 99,
    "tests_failed": 1,
}
# Written before ADR-051: no source field at all.
LEGACY = {
    "type": "test_run",
    "scope": "full-suite",
    "test_command": "pytest tests/",
    "duration_seconds": 999.0,
    "exit_code": 0,
    "result": "success",
    "tests_total": 500,
    "tests_passed": 500,
    "tests_failed": 0,
}


def _helpers_source() -> str:
    """Return the provenance helper block from index.html."""
    text = PANEL_HTML.read_text(encoding="utf-8")
    start = text.index(MARK_START)
    end = text.index(MARK_END)
    return text[start:end]


def _evaluate(expression: str, records: list[dict]) -> object:
    """Evaluate ``expression`` against ``records`` (bound as ``tests``) in node."""
    script = (
        _helpers_source()
        + f"\nconst tests = {json.dumps(records)};\n"
        + f"console.log(JSON.stringify({expression}));\n"
    )
    proc = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        pytest.fail(f"node evaluation failed: {proc.stderr}")
    return json.loads(proc.stdout)


def test_timing_aggregate_ignores_claimed_records():
    """Adding claimed records does not move the observed timing figures."""
    observed_only = _evaluate("observedTestStats(tests)", [OBSERVED, OBSERVED])
    with_claims = _evaluate(
        "observedTestStats(tests)", [OBSERVED, CLAIMED, OBSERVED, CLAIMED]
    )
    assert observed_only == with_claims
    assert observed_only["runs"] == 2
    assert observed_only["totalSeconds"] == 80.0
    assert observed_only["meanSeconds"] == 40.0
    assert observed_only["passRate"] == 1.0


def test_count_aggregate_ignores_observed_records():
    """Adding observed records does not move the claimed test counts."""
    claimed_only = _evaluate("claimedTestCounts(tests)", [CLAIMED])
    with_observed = _evaluate("claimedTestCounts(tests)", [CLAIMED, OBSERVED, OBSERVED])
    assert claimed_only == with_observed
    assert claimed_only == {"total": 100, "passed": 99, "failed": 1}


def test_legacy_record_without_source_excluded_from_both_aggregates():
    """A pre-ADR-051 record is provenance-unknown, not inferred by field shape."""
    assert _evaluate("observedTestStats(tests)", [LEGACY])["runs"] == 0
    assert _evaluate("claimedTestCounts(tests)", [LEGACY]) == {
        "total": 0,
        "passed": 0,
        "failed": 0,
    }


def test_legacy_record_rendered_as_provenance_unknown():
    """Unlabeled records render as unknown rather than being hidden or guessed."""
    assert _evaluate("testRunProvenance(tests[0])", [LEGACY]) == "unknown"
    assert _evaluate("testRunProvenance(tests[0])", [OBSERVED]) == "observed"
    assert _evaluate("testRunProvenance(tests[0])", [CLAIMED]) == "claimed"
    # A record carrying an unrecognised source value is unknown, not trusted.
    assert _evaluate("testRunProvenance(tests[0])", [{"source": "guessed"}]) == "unknown"


def test_observed_pass_rate_counts_failures():
    """Pass rate is measured over observed runs that reached a decision."""
    failed = {**OBSERVED, "exit_code": 1, "result": "failure"}
    stats = _evaluate("observedTestStats(tests)", [OBSERVED, OBSERVED, OBSERVED, failed])
    assert stats["decided"] == 4
    assert stats["passed"] == 3
    assert stats["passRate"] == 0.75


def test_observed_stats_are_null_when_nothing_was_observed():
    """No observed runs means no figure, not a zero (ADR-031 null honesty)."""
    stats = _evaluate("observedTestStats(tests)", [CLAIMED, LEGACY])
    assert stats["runs"] == 0
    assert stats["passRate"] is None
    assert stats["meanSeconds"] is None


def test_timeline_rows_labeled_with_provenance():
    """Every individually rendered test_run row carries its provenance."""
    html = PANEL_HTML.read_text(encoding="utf-8")
    assert 'data-testid="timeline-provenance"' in html
    assert 'data-testid="test-run-provenance"' in html
    # Both rows derive the label from the tested helper, not an inline guess.
    assert html.count("testRunProvenance(") >= 4


def test_panel_aggregate_labels_state_their_provenance():
    """The panel says which population each figure is computed over."""
    html = PANEL_HTML.read_text(encoding="utf-8")
    assert "Tests (claimed)" in html
    assert "Observed pass rate" in html


def test_header_cells_forward_their_attributes():
    """``Th`` must spread props, or the provenance tooltips render as nothing.

    The "Tests (claimed)" headers pass ``title`` to explain where the counts
    come from. A ``Th`` that destructures only ``children``/``className``
    swallows it silently — the column still renders, so nothing fails except
    the explanation.
    """
    html = PANEL_HTML.read_text(encoding="utf-8")
    signature = html[html.index("function Th(") : html.index("function Td(")]
    assert "...props" in signature, "Th drops unknown props (e.g. title)"
    assert "{...props}" in signature, "Th does not spread props onto the <th>"
    # The headers that depend on it.
    assert '<Th title="Test counts come from QA verdicts' in html

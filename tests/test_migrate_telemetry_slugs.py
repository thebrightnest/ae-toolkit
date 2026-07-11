"""Integration tests for scripts/migrate-telemetry-slugs.py.

The script is exercised via subprocess against a tmp fixture archive — never
the real ``~/.aet`` tree. Flags ``--archive``/``--reports`` point both roots
at the fixture, so the inherited ``AET_*`` env vars are irrelevant.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "migrate-telemetry-slugs.py"

OLD_SLUG = "thebrightnest/ae-toolkit"
NEW_SLUG = "aiskills/main"


def run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def make_run(archive: Path, slug: str, date: str, run_id: str, content: str) -> Path:
    run_dir = archive / slug / date / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "record.jsonl").write_text(content)
    return run_dir


def test_dry_run_lists_renames_and_touches_nothing(tmp_path):
    archive = tmp_path / "telemetry"
    reports = tmp_path / "reports"
    old_run = make_run(archive, OLD_SLUG, "2026-07-01", "run-001", '{"a": 1}')

    result = run_script(OLD_SLUG, NEW_SLUG, "--archive", str(archive), "--reports", str(reports))

    assert result.returncode == 0, result.stderr
    # stdout names the pending move
    assert str(archive / OLD_SLUG) in result.stdout
    assert str(archive / NEW_SLUG) in result.stdout
    # fixture archive unchanged
    assert old_run.is_dir()
    assert (old_run / "record.jsonl").read_text() == '{"a": 1}'
    assert not (archive / NEW_SLUG).exists()


def test_apply_renames_and_is_idempotent(tmp_path):
    archive = tmp_path / "telemetry"
    reports = tmp_path / "reports"
    make_run(archive, OLD_SLUG, "2026-07-01", "run-001", '{"a": 1}')
    make_run(archive, OLD_SLUG, "2026-07-02", "run-002", '{"b": 2}')

    result = run_script(
        OLD_SLUG, NEW_SLUG, "--apply", "--archive", str(archive), "--reports", str(reports)
    )

    assert result.returncode == 0, result.stderr
    assert not (archive / OLD_SLUG).exists()
    moved_1 = archive / NEW_SLUG / "2026-07-01" / "run-001" / "record.jsonl"
    moved_2 = archive / NEW_SLUG / "2026-07-02" / "run-002" / "record.jsonl"
    assert moved_1.read_text() == '{"a": 1}'
    assert moved_2.read_text() == '{"b": 2}'
    # empty old parent dirs removed
    assert not (archive / "thebrightnest").exists()

    # second apply: OLD absent + NEW present → nothing to do, exit 0
    result = run_script(
        OLD_SLUG, NEW_SLUG, "--apply", "--archive", str(archive), "--reports", str(reports)
    )
    assert result.returncode == 0, result.stderr
    assert "nothing to do" in result.stdout.lower()


def test_collision_refuses_overwrite(tmp_path):
    archive = tmp_path / "telemetry"
    reports = tmp_path / "reports"
    old_run = make_run(archive, OLD_SLUG, "2026-07-01", "run-001", '{"old": true}')
    new_run = make_run(archive, NEW_SLUG, "2026-07-01", "run-001", '{"new": true}')

    result = run_script(
        OLD_SLUG, NEW_SLUG, "--apply", "--archive", str(archive), "--reports", str(reports)
    )

    assert result.returncode != 0
    # source and destination both intact — never clobber
    assert (old_run / "record.jsonl").read_text() == '{"old": true}'
    assert (new_run / "record.jsonl").read_text() == '{"new": true}'


def test_apply_renames_reports_tree_too(tmp_path):
    archive = tmp_path / "telemetry"
    reports = tmp_path / "reports"
    make_run(archive, OLD_SLUG, "2026-07-01", "run-001", '{"a": 1}')
    verdict = reports / OLD_SLUG / "thp-01" / "verdict.json"
    verdict.parent.mkdir(parents=True)
    verdict.write_text('{"verdict": "pass"}')

    result = run_script(
        OLD_SLUG, NEW_SLUG, "--apply", "--archive", str(archive), "--reports", str(reports)
    )

    assert result.returncode == 0, result.stderr
    assert (reports / NEW_SLUG / "thp-01" / "verdict.json").read_text() == '{"verdict": "pass"}'
    assert not (reports / OLD_SLUG).exists()

    # absent reports dir is not an error
    no_reports = tmp_path / "no-such-reports"
    make_run(archive / "second", OLD_SLUG, "2026-07-03", "run-003", '{"c": 3}')
    result = run_script(
        OLD_SLUG,
        NEW_SLUG,
        "--apply",
        "--archive",
        str(archive / "second"),
        "--reports",
        str(no_reports),
    )
    assert result.returncode == 0, result.stderr
    assert (archive / "second" / NEW_SLUG / "2026-07-03" / "run-003").is_dir()
    assert not no_reports.exists()

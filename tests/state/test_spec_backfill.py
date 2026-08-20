"""Tests for backfilling the portable plan spec into pre-R-19 task records.

The migration recovers each record's plan from a git revision that still has
the file, so a board whose plan files were deleted stays runnable. Every test
runs against a real temporary git repository — git is the migration's source,
not a detail to mock away.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aet import spec_backfill

PLAN_TEMPLATE = """---
id: {task_id}
size: {size}
pipeline: {pipeline}
security_review: {security_review}
docs_sync: {docs_sync}
work_class: normal
blocked_by: []
---

# Plan: {title}

## Context

PRD: docs/prds/open-work-board-prd.md

## Task List

1. Do the work (traces: R-19)

---

*Stage: plan-approved*
"""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


def _plan(task_id: str, **overrides: str) -> str:
    fields = {
        "task_id": task_id,
        "size": "M",
        "pipeline": "full",
        "security_review": "required",
        "docs_sync": "required",
        "title": f"Title for {task_id}",
    }
    fields.update(overrides)
    return PLAN_TEMPLATE.format(**fields)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo whose plan files exist at HEAD~1 and are deleted at HEAD.

    This is the shape ``b95538dd`` left behind: the source is one commit back.
    """
    root = tmp_path / "repo"
    plans = root / "docs" / "plans"
    plans.mkdir(parents=True)
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    for task_id in ("owb-03", "owb-04"):
        (plans / f"{task_id}.md").write_text(_plan(task_id), encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "plans exist")
    for task_id in ("owb-03", "owb-04"):
        (plans / f"{task_id}.md").unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "delete the plans")
    return root


def _task(task_id: str, **extra) -> dict:
    task = {
        "id": task_id,
        "title": f"Title for {task_id}",
        "plan_file": f"docs/plans/{task_id}.md",
        "state": "ready",
    }
    task.update(extra)
    return task


class TestBackfillSpecs:
    def test_record_without_spec_recovers_its_plan_from_the_revision(self, repo: Path):
        queue = [_task("owb-03")]

        result = spec_backfill.backfill_specs(queue, rev="HEAD~1", repo_root=repo)

        assert result.filled == ["owb-03"]
        spec = queue[0]["spec"]
        assert spec["title"] == "Plan: Title for owb-03"
        assert spec["tasks"] == ["1. Do the work (traces: R-19)"]
        assert "## Context" in spec["body"]

    def test_unrecoverable_plan_is_reported_and_the_rest_still_fill(self, repo: Path):
        """A record naming a plan that never existed must not stop the migration."""
        queue = [_task("owb-03"), _task("ghost-99"), _task("owb-04")]

        result = spec_backfill.backfill_specs(queue, rev="HEAD~1", repo_root=repo)

        assert result.filled == ["owb-03", "owb-04"]
        assert [task_id for task_id, _ in result.skipped] == ["ghost-99"]
        assert "docs/plans/ghost-99.md" in result.skipped[0][1]
        assert "spec" not in queue[1]
        assert isinstance(queue[0]["spec"], dict)
        assert isinstance(queue[2]["spec"], dict)

    def test_plan_added_after_the_revision_is_read_from_the_working_tree(self, repo: Path):
        """A plan that postdates the source revision exists only on disk."""
        (repo / "docs" / "plans" / "owb-15.md").write_text(
            _plan("owb-15", title="Added later"), encoding="utf-8"
        )
        queue = [_task("owb-15")]

        result = spec_backfill.backfill_specs(queue, rev="HEAD~1", repo_root=repo)

        assert result.filled == ["owb-15"]
        assert queue[0]["spec"]["title"] == "Plan: Added later"

    def test_a_record_that_already_has_a_spec_is_left_alone(self, repo: Path):
        """Re-running the migration is a no-op."""
        queue = [_task("owb-03")]
        spec_backfill.backfill_specs(queue, rev="HEAD~1", repo_root=repo)
        first_spec = queue[0]["spec"]

        result = spec_backfill.backfill_specs(queue, rev="HEAD~1", repo_root=repo)

        assert result.filled == []
        assert result.already == ["owb-03"]
        assert queue[0]["spec"] == first_spec

    def test_recovered_spec_carries_the_gate_keys_the_file_declared(self, repo: Path):
        """The routing keys are what make the record executable; they must survive."""
        plans = repo / "docs" / "plans"
        plans.mkdir(parents=True, exist_ok=True)
        (plans / "owb-11.md").write_text(
            _plan(
                "owb-11",
                size="S",
                pipeline="minimal",
                security_review="skipped",
                docs_sync="skipped",
            ),
            encoding="utf-8",
        )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add owb-11")
        (plans / "owb-11.md").unlink()
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "delete owb-11")
        queue = [_task("owb-11")]

        spec_backfill.backfill_specs(queue, rev="HEAD~1", repo_root=repo)

        frontmatter = queue[0]["spec"]["frontmatter"]
        assert frontmatter["security_review"] == "skipped"
        assert frontmatter["docs_sync"] == "skipped"
        assert frontmatter["pipeline"] == "minimal"
        assert frontmatter["size"] == "S"


class TestSourceRevision:
    """The source revision is an input that can be wrong or simply absent."""

    def test_an_unresolvable_revision_is_named_rather_than_blamed_on_each_record(
        self, repo: Path
    ):
        """A bad --rev must not read as a corpus where every plan is missing.

        A typo, or a shallow clone that does not reach the revision, makes
        every lookup miss. Reported per record it is indistinguishable from a
        genuinely unrecoverable plan, and the migration exits having silently
        done nothing.
        """
        queue = [_task("owb-03")]

        result = spec_backfill.backfill_specs(
            queue, rev="deadbeef~1", repo_root=repo
        )

        assert result.rev_available is False
        assert result.filled == []
        assert "not in this clone" in result.skipped[0][1]

    def test_a_resolvable_revision_reports_itself_as_available(self, repo: Path):
        result = spec_backfill.backfill_specs([_task("owb-03")], rev="HEAD~1", repo_root=repo)

        assert result.rev_available is True

    def test_a_plan_with_non_ascii_text_recovers_under_a_c_locale(self, repo: Path):
        """Plans carry em-dashes and status glyphs; CI containers carry no locale.

        Decoding the git blob by the process locale raises UnicodeDecodeError
        under LC_ALL=C and takes the whole migration down — every record, not
        just the one being read.
        """
        plans = repo / "docs" / "plans"
        (plans / "owb-20.md").write_text(
            _plan("owb-20", title="Émoji ⚠️ — dashes"), encoding="utf-8"
        )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add owb-20")
        (plans / "owb-20.md").unlink()
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "delete owb-20")

        script = (
            "import json, sys\n"
            "from aet import spec_backfill\n"
            "queue = [{'id': 'owb-20', 'plan_file': 'docs/plans/owb-20.md'}]\n"
            f"r = spec_backfill.backfill_specs(queue, rev='HEAD~1', repo_root={str(repo)!r})\n"
            "print(json.dumps({'filled': r.filled, 'title': queue[0]['spec']['title']}))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={
                **os.environ,
                "LC_ALL": "C",
                "LANG": "C",
                "PYTHONUTF8": "0",
                "PYTHONCOERCECLOCALE": "0",
            },
        )

        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
        assert payload["filled"] == ["owb-20"]
        assert "Émoji" in payload["title"]


class TestRecordsMissingSpec:
    """The standing guard: a record without a portable spec is not executable."""

    def test_names_every_record_without_a_spec(self):
        queue = [
            _task("owb-03", spec={"frontmatter": {}, "title": "t", "body": "", "tasks": []}),
            _task("owb-04"),
            _task("owb-05", spec=None),
        ]

        assert spec_backfill.records_missing_spec(queue) == ["owb-04", "owb-05"]

    def test_empty_when_every_record_carries_a_spec(self):
        queue = [
            _task("owb-03", spec={"frontmatter": {}, "title": "t", "body": "", "tasks": []})
        ]

        assert spec_backfill.records_missing_spec(queue) == []

    def test_a_spec_that_is_not_a_mapping_does_not_count(self):
        """A truthy non-dict would pass a bare presence check and fail at render."""
        queue = [_task("owb-03", spec="docs/plans/owb-03.md")]

        assert spec_backfill.records_missing_spec(queue) == ["owb-03"]


class TestArchiveFallback:
    """Legacy plans survive only in ``docs/plans/archive/`` after removal."""

    def test_archive_plan_is_used_when_revision_and_disk_miss(self, repo: Path):
        archive = repo / "docs" / "plans" / "archive"
        archive.mkdir(parents=True)
        (archive / "owb-03.md").write_text(
            _plan("owb-03", size="S"), encoding="utf-8"
        )
        queue = [_task("owb-03")]

        result = spec_backfill.backfill_specs(
            queue, rev="deadbeef~1", repo_root=repo
        )

        assert result.filled == ["owb-03"]
        assert queue[0]["spec"]["frontmatter"]["size"] == "S"

    def test_working_tree_is_preferred_over_archive(self, repo: Path):
        plans = repo / "docs" / "plans"
        archive = plans / "archive"
        archive.mkdir(parents=True)
        (archive / "owb-03.md").write_text(
            _plan("owb-03", size="S"), encoding="utf-8"
        )
        (plans / "owb-03.md").write_text(
            _plan("owb-03", size="L"), encoding="utf-8"
        )
        queue = [_task("owb-03")]

        spec_backfill.backfill_specs(queue, rev="deadbeef~1", repo_root=repo)

        assert queue[0]["spec"]["frontmatter"]["size"] == "L"

    def test_revision_is_preferred_over_archive(self, repo: Path):
        archive = repo / "docs" / "plans" / "archive"
        archive.mkdir(parents=True)
        (archive / "owb-03.md").write_text(
            _plan("owb-03", size="S"), encoding="utf-8"
        )
        queue = [_task("owb-03")]

        spec_backfill.backfill_specs(queue, rev="HEAD~1", repo_root=repo)

        assert queue[0]["spec"]["frontmatter"]["size"] == "M"

    def test_unrecoverable_record_reports_archive_was_consulted(self, repo: Path):
        archive = repo / "docs" / "plans" / "archive"
        archive.mkdir(parents=True)
        queue = [_task("ghost-99")]

        result = spec_backfill.backfill_specs(
            queue, rev="deadbeef~1", repo_root=repo
        )

        assert result.skipped[0][1].startswith(
            "no plan at deadbeef~1 (not in this clone), on disk, or in archive"
        )

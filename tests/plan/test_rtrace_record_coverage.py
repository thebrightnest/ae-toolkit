"""R-trace coverage read from task records, not only the authoring corpus.

A plan file is an authoring artifact; after intake the record carries the spec
(ADR-061). Coverage is the one r-trace property that outlives authoring — the
siblings that already delivered a PRD's requirements have left ``docs/plans/``
— so a coverage union built from the directory alone asks a new plan to trace
requirements another plan already covered.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from aet import plan_validate


def _record(task_id: str, prd: str, traces: list[str]) -> dict:
    tasks = "\n".join(
        f"{i}. Do the thing (traces: {rid})." for i, rid in enumerate(traces, 1)
    )
    return {
        "id": task_id,
        "spec": {
            "title": task_id,
            "body": f"## Context\n\nPRD: {prd}\n\n## Task List\n\n{tasks}\n",
            "tasks": f"## Task List\n\n{tasks}\n",
        },
    }


class TestRecordCoverage(unittest.TestCase):
    """`record_coverage` maps each record's traces onto the PRD it references."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_record_contributes_its_traces_to_its_prd(self):
        result = plan_validate.record_coverage(
            [_record("t1", "docs/prds/alpha.md", ["R-1", "R-2"])], self.root
        )

        self.assertEqual(
            result.coverage, {self.root / "docs" / "prds" / "alpha.md": {"R-1", "R-2"}}
        )
        self.assertEqual(result.unreadable, ())

    def test_records_sharing_a_prd_union_their_traces(self):
        result = plan_validate.record_coverage(
            [
                _record("t1", "docs/prds/alpha.md", ["R-1"]),
                _record("t2", "docs/prds/alpha.md", ["R-2"]),
            ],
            self.root,
        )

        self.assertEqual(
            result.coverage, {self.root / "docs" / "prds" / "alpha.md": {"R-1", "R-2"}}
        )

    def test_records_for_different_prds_stay_separate(self):
        result = plan_validate.record_coverage(
            [
                _record("t1", "docs/prds/alpha.md", ["R-1"]),
                _record("t2", "docs/prds/beta.md", ["R-1"]),
            ],
            self.root,
        )

        self.assertEqual(len(result.coverage), 2)

    def test_a_record_without_a_spec_is_named_not_skipped(self):
        """An uncovered requirement caused by a missing spec is not the plan's fault."""
        result = plan_validate.record_coverage(
            [{"id": "pre-r19"}, _record("t1", "docs/prds/alpha.md", ["R-1"])],
            self.root,
        )

        self.assertEqual(result.unreadable, ("pre-r19",))
        self.assertEqual(len(result.coverage), 1)

    def test_a_record_whose_spec_names_no_prd_is_named(self):
        result = plan_validate.record_coverage(
            [{"id": "no-prd", "spec": {"body": "## Context\n\nnothing", "tasks": ""}}],
            self.root,
        )

        self.assertEqual(result.unreadable, ("no-prd",))
        self.assertEqual(result.coverage, {})

    def test_a_list_valued_tasks_field_is_read(self):
        record = _record("t1", "docs/prds/alpha.md", ["R-1"])
        record["spec"]["tasks"] = ["1. Do the thing (traces: R-1)."]

        result = plan_validate.record_coverage([record], self.root)

        self.assertEqual(
            result.coverage, {self.root / "docs" / "prds" / "alpha.md": {"R-1"}}
        )


class TestSettledSiblingsCountTowardCoverage(unittest.TestCase):
    """The end-to-end property OI-05 names: a merged sibling still counts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.plans = self.root / "docs" / "plans"
        self.prds = self.root / "docs" / "prds"
        self.plans.mkdir(parents=True)
        self.prds.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.prds / "alpha.md").write_text(
            "# Alpha\n## Requirements\n- **R-1**: one\n- **R-2**: two\n", encoding="utf-8"
        )
        (self.plans / "live.md").write_text(
            "---\nid: live\nsize: S\n---\n\n# Plan live\n\n## Context\n\n"
            "PRD: docs/prds/alpha.md\n\n## Task List\n\n1. Deliver (traces: R-1).\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _rtrace(self, extra_coverage=None):
        findings = plan_validate.validate(
            [self.plans / "live.md"],
            repo_root=self.root,
            extra_coverage=extra_coverage,
        )
        return [f for f in findings if f.check_id == "rtrace"]

    def test_without_the_record_the_settled_sibling_is_invisible(self):
        rtrace = self._rtrace()

        self.assertEqual(len(rtrace), 1)
        self.assertIn("R-2 has no covering task", rtrace[0].message)

    def test_the_settled_siblings_record_covers_the_requirement(self):
        settled = plan_validate.record_coverage(
            [_record("settled", "docs/prds/alpha.md", ["R-2"])], self.root
        )

        self.assertEqual(self._rtrace(extra_coverage=settled.coverage), [])

    def test_a_requirement_no_one_delivered_is_still_reported(self):
        (self.prds / "alpha.md").write_text(
            "# Alpha\n## Requirements\n"
            "- **R-1**: one\n- **R-2**: two\n- **R-3**: three\n",
            encoding="utf-8",
        )
        settled = plan_validate.record_coverage(
            [_record("settled", "docs/prds/alpha.md", ["R-2"])], self.root
        )

        rtrace = self._rtrace(extra_coverage=settled.coverage)

        self.assertEqual(len(rtrace), 1)
        self.assertIn("R-3 has no covering task", rtrace[0].message)


class TestCoverageFromBackend(unittest.TestCase):
    """Reading the store degrades to a named reason, never to a raise."""

    def test_an_unreadable_store_yields_a_reason_not_an_exception(self):
        class _Broken:
            def load(self, verify=True):
                raise RuntimeError("no repository here")

        result = plan_validate.coverage_from_backend(_Broken(), Path("/tmp"))

        self.assertEqual(result.coverage, {})
        self.assertIn("no repository here", result.source_error)

    def test_live_and_sealed_records_are_both_read(self):
        root = Path("/repo")

        class _Store:
            def load(self, verify=True):
                return {"queue": [_record("live", "docs/prds/alpha.md", ["R-1"])]}

            def settled_ids(self):
                return {"gone"}

            def read_sealed(self, task_id):
                return _record(task_id, "docs/prds/alpha.md", ["R-2"])

        result = plan_validate.coverage_from_backend(_Store(), root)

        self.assertEqual(
            result.coverage, {root / "docs" / "prds" / "alpha.md": {"R-1", "R-2"}}
        )
        self.assertEqual(result.source_error, "")


if __name__ == "__main__":
    unittest.main()

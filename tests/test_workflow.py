"""Tests for the workflow schema, packaged default, and loader."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import workflow as workflow_module  # noqa: E402
from workflow import WorkflowError, load_workflow  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent

PACKAGED_PATH = REPO_ROOT / "aet-work" / "workflows" / "software.json"


def packaged_document():
    """Return a deep copy of the packaged default workflow document."""
    return json.loads(PACKAGED_PATH.read_text(encoding="utf-8"))


class WorkflowFileTestCase(unittest.TestCase):
    """Base case that materializes a workflow document into a tmp repo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_workflow(self, document, name="software"):
        workflow_dir = self.repo_root / ".agents" / "workflows"
        workflow_dir.mkdir(parents=True, exist_ok=True)
        path = workflow_dir / f"{name}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path


class TestPackagedDefault(unittest.TestCase):
    def test_entry_stage_is_first_stage(self):
        wf = load_workflow(REPO_ROOT)
        self.assertEqual(wf.entry_stage, "plan-approved")

    def test_stage_sequence_is_the_software_pipeline(self):
        wf = load_workflow(REPO_ROOT)
        self.assertEqual(
            [s.name for s in wf.stages],
            ["plan-approved", "implemented", "qa-complete", "reviewed", "secure", "synced"],
        )


class TestNextStage(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(REPO_ROOT)

    def test_list_order_succession(self):
        names = [s.name for s in self.wf.stages]
        for current, expected in zip(names, names[1:]):
            self.assertEqual(self.wf.next_stage(current), expected)

    def test_last_stage_advances_to_done_state(self):
        self.assertEqual(self.wf.next_stage("synced"), "done")

    def test_done_state_has_no_successor(self):
        self.assertIsNone(self.wf.next_stage("done"))

    def test_unknown_stage_raises(self):
        with self.assertRaisesRegex(WorkflowError, "Unknown stage"):
            self.wf.next_stage("bogus")


class TestSessionGroups(unittest.TestCase):
    def setUp(self):
        self.wf = load_workflow(REPO_ROOT)

    def _names(self, groups):
        return [[s.name for s in group] for group in groups]

    def test_standard_uses_declared_groups(self):
        self.assertEqual(
            self._names(self.wf.session_groups("standard")),
            [["plan-approved", "implemented"], ["qa-complete"], ["reviewed", "secure"]],
        )

    def test_minimal_is_single_session_of_skilled_stages(self):
        self.assertEqual(
            self._names(self.wf.session_groups("minimal")),
            [["plan-approved", "implemented", "qa-complete", "reviewed", "secure"]],
        )

    def test_full_is_one_session_per_skilled_stage(self):
        self.assertEqual(
            self._names(self.wf.session_groups("full")),
            [["plan-approved"], ["implemented"], ["qa-complete"], ["reviewed"], ["secure"]],
        )

    def test_default_isolation_is_standard(self):
        self.assertEqual(
            self._names(self.wf.session_groups()),
            self._names(self.wf.session_groups("standard")),
        )

    def test_unknown_isolation_raises(self):
        with self.assertRaisesRegex(WorkflowError, "Unknown isolation level"):
            self.wf.session_groups("bogus")


class TestResolutionOrder(WorkflowFileTestCase):
    def test_repo_override_wins_over_packaged(self):
        document = packaged_document()
        document["name"] = "custom-software"
        document["done_state"] = "shipped"
        self.write_workflow(document)
        wf = load_workflow(self.repo_root)
        self.assertEqual(wf.name, "custom-software")
        self.assertEqual(wf.done_state, "shipped")

    def test_packaged_used_when_repo_has_no_override(self):
        wf = load_workflow(self.repo_root)
        self.assertEqual(wf.name, "software")
        self.assertEqual(wf.entry_stage, "plan-approved")

    def test_missing_workflow_raises(self):
        with self.assertRaisesRegex(WorkflowError, "not found"):
            load_workflow(self.repo_root, "nonexistent")


class TestValidationRules(WorkflowFileTestCase):
    """One failure test per structural validation rule."""

    def load_document(self, document):
        self.write_workflow(document)
        return load_workflow(self.repo_root)

    def test_unknown_evidence_kind_rejected(self):
        document = packaged_document()
        document["stages"][1]["evidence"] = "vibes"
        with self.assertRaisesRegex(WorkflowError, "unknown evidence kind"):
            self.load_document(document)

    def test_duplicate_stage_rejected(self):
        document = packaged_document()
        document["stages"].append(copy.deepcopy(document["stages"][0]))
        with self.assertRaisesRegex(WorkflowError, "Duplicate stage"):
            self.load_document(document)

    def test_group_referencing_unknown_stage_rejected(self):
        document = packaged_document()
        document["execution_policy"]["session_groups"][0].append("ghost")
        with self.assertRaisesRegex(WorkflowError, "unknown stage"):
            self.load_document(document)

    def test_group_containing_skill_less_stage_rejected(self):
        document = packaged_document()
        document["execution_policy"]["session_groups"][0].append("synced")
        with self.assertRaisesRegex(WorkflowError, "skill-less stage"):
            self.load_document(document)

    def test_group_partition_must_cover_every_skilled_stage(self):
        document = packaged_document()
        document["execution_policy"]["session_groups"] = [["plan-approved", "implemented"]]
        with self.assertRaisesRegex(WorkflowError, "partition"):
            self.load_document(document)

    def test_stage_in_two_groups_rejected(self):
        document = packaged_document()
        document["execution_policy"]["session_groups"][1].append("implemented")
        with self.assertRaisesRegex(WorkflowError, "more than one session group"):
            self.load_document(document)

    def test_bad_routing_shape_rejected(self):
        document = packaged_document()
        document["routing"]["default"] = "claude"
        with self.assertRaisesRegex(WorkflowError, "routing.default"):
            self.load_document(document)

    def test_routing_override_referencing_unknown_stage_rejected(self):
        document = packaged_document()
        document["routing"]["by_stage"] = {"ghost": {"harness": "claude", "model": None}}
        with self.assertRaisesRegex(WorkflowError, "unknown stage"):
            self.load_document(document)

    def test_unsupported_version_rejected(self):
        document = packaged_document()
        document["version"] = 2
        with self.assertRaisesRegex(WorkflowError, "Unsupported workflow version"):
            self.load_document(document)

    def test_invalid_json_rejected(self):
        path = self.write_workflow(packaged_document())
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaisesRegex(WorkflowError, "Cannot read workflow"):
            load_workflow(self.repo_root)


class TestRouting(WorkflowFileTestCase):
    def test_default_routing_exposed(self):
        wf = load_workflow(REPO_ROOT)
        self.assertEqual(wf.routing.default, {"harness": "claude", "model": None})
        self.assertEqual(wf.routing.by_stage, {})

    def test_stage_override_exposed(self):
        document = packaged_document()
        document["routing"]["by_stage"] = {
            "qa-complete": {"harness": "codex", "model": "gpt-5"}
        }
        self.write_workflow(document)
        wf = load_workflow(self.repo_root)
        self.assertEqual(
            wf.routing.by_stage["qa-complete"], {"harness": "codex", "model": "gpt-5"}
        )


class TestExtensionKeys(WorkflowFileTestCase):
    def test_unknown_keys_tolerated_and_preserved(self):
        document = packaged_document()
        document["context_fidelity"] = {"mode": "full"}
        document["stages"][0]["warmup"] = True
        document["execution_policy"]["handoff"] = "compact"
        document["routing"]["fallback"] = {"harness": "gemini"}
        self.write_workflow(document)
        wf = load_workflow(self.repo_root)
        self.assertEqual(wf.extra["context_fidelity"], {"mode": "full"})
        self.assertTrue(wf.stage_map["plan-approved"].extra["warmup"])
        self.assertEqual(wf.execution_policy.extra["handoff"], "compact")
        self.assertEqual(wf.routing.extra["fallback"], {"harness": "gemini"})


class TestPackagedBaseline(unittest.TestCase):
    """Literal baseline pins for the packaged software workflow.

    Migrated from the pipeline.py parity assertions (wfd-03): with the table
    deleted, the packaged file is its own baseline — sequence, skills,
    evidence, gate keys, and session groups stated literally here.
    """

    # (name, skills, evidence, gate_key) — one row per stage, in list order.
    EXPECTED_STAGES = [
        ("plan-approved", ["aet-tdd", "aet-implement"], None, None),
        ("implemented", ["aet-qa"], "qa", None),
        ("qa-complete", ["aet-review"], "review", None),
        ("reviewed", ["aet-cso"], "cso", "security_review"),
        ("secure", ["aet-sync-docs"], "sync-docs", "docs_sync"),
        ("synced", [], None, None),
    ]

    def setUp(self):
        self.wf = load_workflow(REPO_ROOT)

    def test_sequence_skills_evidence_and_gate_keys(self):
        self.assertEqual(
            [(s.name, s.skills, s.evidence, s.gate_key) for s in self.wf.stages],
            [tuple(row) for row in self.EXPECTED_STAGES],
        )

    def test_stage_map_membership(self):
        for name, *_ in self.EXPECTED_STAGES:
            self.assertIn(name, self.wf.stage_map)

    def test_entry_stage_and_done_state(self):
        self.assertEqual(self.wf.entry_stage, "plan-approved")
        self.assertEqual(self.wf.done_state, "done")

    def test_terminal_advancement_to_done_state(self):
        self.assertEqual(self.wf.next_stage("synced"), "done")
        self.assertIsNone(self.wf.next_stage("done"))

    def test_next_stage_chain(self):
        names = [name for name, *_ in self.EXPECTED_STAGES]
        for current, expected in zip(names, names[1:]):
            self.assertEqual(self.wf.next_stage(current), expected)

    def _names(self, groups):
        return [[s.name for s in group] for group in groups]

    def test_session_groups_standard(self):
        self.assertEqual(
            self._names(self.wf.session_groups("standard")),
            [["plan-approved", "implemented"], ["qa-complete"], ["reviewed", "secure"]],
        )

    def test_session_groups_minimal(self):
        self.assertEqual(
            self._names(self.wf.session_groups("minimal")),
            [["plan-approved", "implemented", "qa-complete", "reviewed", "secure"]],
        )

    def test_session_groups_full(self):
        self.assertEqual(
            self._names(self.wf.session_groups("full")),
            [["plan-approved"], ["implemented"], ["qa-complete"], ["reviewed"], ["secure"]],
        )

    def test_no_runtime_judgment_left_in_the_engine(self):
        # Routing is data: stages carry no conditionals and the module keeps
        # no heuristic helpers (guard migrated from tests/test_pipeline.py).
        for stage in self.wf.stages:
            self.assertFalse(hasattr(stage, "conditional"))
        self.assertFalse(hasattr(workflow_module, "_security_sensitive"))
        self.assertFalse(hasattr(workflow_module, "_divergences_found"))


if __name__ == "__main__":
    unittest.main()

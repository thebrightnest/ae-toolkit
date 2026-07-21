"""Tests for the merge-time workflow lint (src/aet/cli/validate-workflows.py).

One failing fixture per lint rule, plus the packaged default green through
the CLI entry point. The lint reuses workflow.py's validation core and adds
the merge-time-only skill-resolution check.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]

# Load the lint script (no .py extension) as a module.
_LINT_BIN = REPO_ROOT / "src" / "aet" / "cli" / "validate-workflows.py"
_loader = importlib.machinery.SourceFileLoader("validate_workflows", str(_LINT_BIN))
_spec = importlib.util.spec_from_loader("validate_workflows", _loader)
validate_workflows = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_workflows)

PACKAGED_PATH = REPO_ROOT / "src" / "aet" / "workflows" / "software.json"


def packaged_document():
    """Return a deep copy of the packaged default workflow document."""
    return json.loads(PACKAGED_PATH.read_text(encoding="utf-8"))


class WorkflowLintTestCase(unittest.TestCase):
    """Materialize a workflow document into a tmp repo and lint it."""

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

    def lint_file(self, path):
        return validate_workflows.lint_workflow_file(path, self.repo_root)


class TestStructuralRules(WorkflowLintTestCase):
    """One failing fixture per rule from the shared validation core."""

    def test_unknown_evidence_kind_flagged(self):
        document = packaged_document()
        document["stages"][1]["evidence"] = "vibes"
        path = self.write_workflow(document)
        findings = self.lint_file(path)
        self.assertTrue(any("unknown evidence kind" in f for f in findings), findings)

    def test_duplicate_stage_flagged(self):
        import copy

        document = packaged_document()
        document["stages"].append(copy.deepcopy(document["stages"][0]))
        path = self.write_workflow(document)
        findings = self.lint_file(path)
        self.assertTrue(any("Duplicate stage" in f for f in findings), findings)

    def test_empty_stage_list_flagged(self):
        document = packaged_document()
        document["stages"] = []
        path = self.write_workflow(document)
        findings = self.lint_file(path)
        self.assertTrue(any("non-empty 'stages' list" in f for f in findings), findings)

    def test_unsupported_version_flagged(self):
        document = packaged_document()
        document["version"] = 2
        path = self.write_workflow(document)
        findings = self.lint_file(path)
        self.assertTrue(any("Unsupported workflow version" in f for f in findings), findings)

    def test_session_groups_must_partition_skilled_stages(self):
        document = packaged_document()
        document["execution_policy"]["session_groups"] = [["plan-approved", "implemented"]]
        path = self.write_workflow(document)
        findings = self.lint_file(path)
        self.assertTrue(any("partition" in f for f in findings), findings)

    def test_routing_default_requires_harness(self):
        document = packaged_document()
        document["routing"]["default"] = {"model": None}
        path = self.write_workflow(document)
        findings = self.lint_file(path)
        self.assertTrue(any("routing.default" in f and "harness" in f for f in findings), findings)

    def test_invalid_json_flagged(self):
        path = self.write_workflow(packaged_document())
        path.write_text("{not json", encoding="utf-8")
        findings = self.lint_file(path)
        self.assertTrue(findings)


class TestSkillResolution(WorkflowLintTestCase):
    """The merge-time-only check: every bound skill must resolve on disk."""

    def test_unknown_skill_flagged(self):
        document = packaged_document()
        document["stages"][0]["skills"] = ["aet-nonexistent"]
        path = self.write_workflow(document)
        findings = self.lint_file(path)
        self.assertTrue(
            any("unknown skill" in f and "aet-nonexistent" in f for f in findings), findings
        )

    def test_resolvable_skill_is_clean(self):
        document = packaged_document()
        document["stages"][0]["skills"] = ["content-draft"]
        skills_dir = self.repo_root / "skills"
        skill_md = skills_dir / "content-draft" / "SKILL.md"
        skill_md.parent.mkdir(parents=True)
        skill_md.write_text(
            "---\nname: content-draft\ndescription: stub\n---\n", encoding="utf-8"
        )
        # Only the first stage's bindings changed; the remaining aet-* skills
        # still need stubs for the file to lint clean.
        for skill in ("aet-qa", "aet-review", "aet-cso", "aet-sync-docs"):
            stub = skills_dir / skill / "SKILL.md"
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text(f"---\nname: {skill}\ndescription: stub\n---\n", encoding="utf-8")
        path = self.write_workflow(document)
        self.assertEqual(self.lint_file(path), [])


class TestCLI(WorkflowLintTestCase):
    def test_packaged_default_lints_green(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = validate_workflows.main(["--repo-root", str(REPO_ROOT)])
        self.assertEqual(exit_code, 0)
        self.assertIn("clean", stdout.getvalue())

    def test_failing_repo_workflow_exits_nonzero_with_finding_lines(self):
        document = packaged_document()
        document["stages"][1]["evidence"] = "vibes"
        self.write_workflow(document)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = validate_workflows.main(["--repo-root", str(self.repo_root)])
        self.assertEqual(exit_code, 1)
        output = stdout.getvalue()
        self.assertIn("unknown evidence kind", output)
        self.assertIn("software.json", output)


if __name__ == "__main__":
    unittest.main()

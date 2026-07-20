"""Exit-gate proof: a second team's workflow is expressible as data only.

Loads, lints, groups, and traverses tests/fixtures/workflows/content.json —
a plausible content-team flow with different gates, evidence, and routing —
with zero engine changes. The "no engine module modified" assertion is
structural: this test imports only public engine APIs plus the fixture data.
"""

import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet import (  # noqa: E402
    evidence,
    telemetry,
)
from aet.cli_adapter import CLIAdapter  # noqa: E402
from aet.workflow import load_workflow  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "workflows" / "content.json"

# Load the lint script (no .py extension) as a module.
_LINT_BIN = REPO_ROOT / "aet-work" / "bin" / "validate-workflows"
_lint_loader = importlib.machinery.SourceFileLoader("validate_workflows", str(_LINT_BIN))
_lint_spec = importlib.util.spec_from_loader("validate_workflows", _lint_loader)
validate_workflows = importlib.util.module_from_spec(_lint_spec)
_lint_spec.loader.exec_module(validate_workflows)

# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = REPO_ROOT / "aet-work" / "bin" / "orchestrator"
_orch_loader = importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_BIN))
_orch_spec = importlib.util.spec_from_loader("orchestrator", _orch_loader)
orchestrator = importlib.util.module_from_spec(_orch_spec)
_orch_spec.loader.exec_module(orchestrator)

_FAKE_ADAPTER = CLIAdapter(
    name="test",
    bin="echo",
    prompt_flag="-p",
    workdir_flag=None,
    headless_flag=None,
)

VARIANT_SKILLS = ("content-draft", "content-edit", "content-fact-check")


def _init_git_repo(repo_root: str) -> None:
    """Initialize a git repo with a clean main branch tracking origin."""
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.name", "Test User"],
        check=True,
    )


def _commit_all(repo_root: str, message: str) -> None:
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", message], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


class VariantRepoTestCase(unittest.TestCase):
    """A tmp repo whose .agents/workflows/content.json is the variant fixture."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def install_variant(self):
        """Copy the fixture into the tmp repo and stub its bound skills."""
        workflow_dir = self.repo_root / ".agents" / "workflows"
        workflow_dir.mkdir(parents=True, exist_ok=True)
        variant_path = workflow_dir / "content.json"
        shutil.copy(FIXTURE_PATH, variant_path)
        for skill in VARIANT_SKILLS:
            skill_md = self.repo_root / skill / "SKILL.md"
            skill_md.parent.mkdir(parents=True, exist_ok=True)
            skill_md.write_text(
                f"---\nname: {skill}\ndescription: stub\n---\n", encoding="utf-8"
            )
        return variant_path


class TestVariantLoadsAndLints(VariantRepoTestCase):
    def test_variant_loads_through_the_public_loader(self):
        self.install_variant()
        wf = load_workflow(self.repo_root, "content")
        self.assertEqual(wf.name, "content")
        self.assertEqual(wf.done_state, "live")
        self.assertEqual(
            [(s.name, s.skills, s.evidence, s.gate_key) for s in wf.stages],
            [
                ("draft", ["content-draft"], None, None),
                ("edited", ["content-edit"], None, None),
                ("fact-checked", ["content-fact-check"], "review", "fact_check"),
                ("published", [], None, None),
            ],
        )
        self.assertEqual(wf.entry_stage, "draft")
        self.assertEqual(wf.next_stage("published"), "live")
        self.assertIsNone(wf.next_stage("live"))

    def test_variant_lints_clean_with_stub_skills(self):
        variant_path = self.install_variant()
        findings = validate_workflows.lint_workflow_file(variant_path, self.repo_root)
        self.assertEqual(findings, [])

    def test_variant_rebinds_the_fixed_evidence_menu(self):
        # The variant reuses the kernel "review" kind; it never invents kinds.
        self.install_variant()
        wf = load_workflow(self.repo_root, "content")
        kinds = {s.evidence for s in wf.stages if s.evidence is not None}
        self.assertEqual(kinds, {"review"})
        self.assertIn("review", evidence.SCHEMAS)

    def test_variant_routing_sends_one_stage_to_a_second_harness(self):
        self.install_variant()
        wf = load_workflow(self.repo_root, "content")
        self.assertEqual(wf.routing.default["harness"], "claude")
        self.assertEqual(wf.routing.by_stage["fact-checked"]["harness"], "gemini")


class TestVariantSessionGroups(VariantRepoTestCase):
    def setUp(self):
        super().setUp()
        self.install_variant()
        self.wf = load_workflow(self.repo_root, "content")

    def _names(self, groups):
        return [[s.name for s in group] for group in groups]

    def test_standard_isolation_reflects_the_variant_groups(self):
        self.assertEqual(
            self._names(self.wf.session_groups("standard")),
            [["draft", "edited"], ["fact-checked"]],
        )

    def test_minimal_isolation_is_one_session(self):
        self.assertEqual(
            self._names(self.wf.session_groups("minimal")),
            [["draft", "edited", "fact-checked"]],
        )

    def test_full_isolation_is_one_session_per_skilled_stage(self):
        self.assertEqual(
            self._names(self.wf.session_groups("full")),
            [["draft"], ["edited"], ["fact-checked"]],
        )


class TestVariantTraversal(unittest.TestCase):
    """Orchestrator walks the variant end to end with patched session runners."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _build_repo(self, plan_frontmatter_extra: str) -> str:
        repo_root = self.repo_root
        _init_git_repo(repo_root)
        subprocess.run(
            ["git", "-C", repo_root, "remote", "add", "origin", repo_root],
            check=True,
        )

        # Install the variant workflow and its stub skills.
        workflow_dir = Path(repo_root, ".agents", "workflows")
        workflow_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURE_PATH, workflow_dir / "content.json")
        for skill in VARIANT_SKILLS:
            skill_md = Path(repo_root, skill, "SKILL.md")
            skill_md.parent.mkdir(parents=True, exist_ok=True)
            skill_md.write_text(
                f"---\nname: {skill}\ndescription: stub\n---\n", encoding="utf-8"
            )

        plan_file = Path(repo_root, "docs", "plans", "demo.md")
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        plan_file.write_text(
            "---\n"
            "id: demo\n"
            "workflow: content\n"
            f"{plan_frontmatter_extra}"
            "---\n\n# Demo\n\n_Stage: draft_\n",
            encoding="utf-8",
        )
        _commit_all(repo_root, "variant repo")
        return str(plan_file)

    def _run_task(self, plan_file: str, reports_dir: str, archive_dir: str):
        env = os.environ.copy()
        env["AET_REPORTS_DIR"] = reports_dir
        env["AET_PROJECT_ID"] = "demo/project"
        env["AET_TELEMETRY_ARCHIVE_DIR"] = archive_dir
        env["AET_RUN_ID"] = "run-test"

        # A passing review verdict for the fact-checked stage's evidence gate.
        evidence.write_verdict(
            task_id="demo",
            kind="review",
            record={
                "task_id": "demo",
                "stage": "fact-checked",
                "skill": "content-fact-check",
                "verdict": "pass",
                "summary": "ok",
                "generated_at": "2026-07-11T00:00:00Z",
                "tree_hash": "t0",
                "findings": [],
            },
            project_slug="demo/project",
            reports_root=reports_dir,
        )

        with patch.dict(os.environ, env, clear=False):
            logger = telemetry.RunLogger(self.repo_root, run_id="r1")
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            with patch.object(
                orchestrator, "run_stage_group", return_value=(0, None, None)
            ) as mock_group, patch.object(
                orchestrator, "run_stage", return_value=(0, None, None)
            ) as mock_stage, patch.object(
                orchestrator, "verify_branch_has_commits", return_value=(True, "")
            ), patch.object(
                orchestrator, "verify_stage_advancement", return_value=(True, "")
            ):
                result = orchestrator.process_task(
                    task,
                    self.repo_root,
                    _FAKE_ADAPTER,
                    "standard",
                    logger=logger,
                )
        return result, task, mock_group, mock_stage

    def test_traverses_every_stage_honoring_required_gate(self):
        with tempfile.TemporaryDirectory() as reports_dir:
            with tempfile.TemporaryDirectory() as archive_dir:
                plan_file = self._build_repo("fact_check: required\n")
                result, task, mock_group, mock_stage = self._run_task(
                    plan_file, reports_dir, archive_dir
                )

        self.assertTrue(result)
        # Group session ran draft → edited in one call.
        self.assertEqual(mock_group.call_count, 1)
        group_stages = mock_group.call_args.args[4]
        self.assertEqual([s.name for s in group_stages], ["draft", "edited"])
        # The gated single-stage group ran fact-checked via run_stage,
        # carrying its rebound evidence kind to the session environment.
        self.assertEqual(mock_stage.call_count, 1)
        self.assertEqual(mock_stage.call_args.args[5], "fact-checked")
        self.assertEqual(mock_stage.call_args.kwargs["verdict_kind"], "review")
        # The walk advanced past the variant's final stage.
        self.assertEqual(task["stage"], "published")

    def test_skipped_gate_omits_the_gated_stage(self):
        with tempfile.TemporaryDirectory() as reports_dir:
            with tempfile.TemporaryDirectory() as archive_dir:
                plan_file = self._build_repo("fact_check: skipped\n")
                result, task, mock_group, mock_stage = self._run_task(
                    plan_file, reports_dir, archive_dir
                )

        self.assertTrue(result)
        self.assertEqual(mock_group.call_count, 1)
        # The gated stage was skipped from frontmatter: no per-stage session
        # ran, and the recorded stage stays at the skipped stage.
        mock_stage.assert_not_called()
        self.assertEqual(task["stage"], "fact-checked")


if __name__ == "__main__":
    unittest.main()

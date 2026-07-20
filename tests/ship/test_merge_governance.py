"""Governance tests for the autonomous-merge fail-closed boundary.

These tests verify that the ADR-005 extension and its CONVENTIONS.md mirror are
present, and that aet-ship/SKILL.md states the human-merge boundary clearly and
does not instruct an agent to merge a PR.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
CONVENTIONS_MD = REPO_ROOT / "docs" / "CONVENTIONS.md"
AET_SHIP_SKILL = REPO_ROOT / "aet-ship" / "SKILL.md"
ADR_029 = REPO_ROOT / "docs" / "adr" / "029-autonomous-merge-fail-closed.md"


class TestAutonomousMergeGovernance:
    """Regression tests for the autonomous-merge fail-closed boundary."""

    def test_adr_029_exists_and_extends_adr_005(self):
        """ADR-029 must exist and extend ADR-005's must-stop list."""
        assert ADR_029.exists(), f"Expected ADR-029 to exist: {ADR_029}"
        content = ADR_029.read_text()
        lower = content.lower()
        assert "adr-005" in lower, "ADR-029 must reference ADR-005"
        assert "extends" in lower, "ADR-029 must state it extends ADR-005"
        assert "autonomous merge" in lower, "ADR-029 must mention autonomous merge"
        assert "fail-closed" in lower, "ADR-029 must state fail-closed posture"

    def test_conventions_lists_autonomous_merge_must_stop(self):
        """CONVENTIONS.md must list autonomous merge as a must-stop gate and cite ADR-029."""
        content = CONVENTIONS_MD.read_text()
        must_stop_section = content.split("## Gates That Must Still Stop in Unattended Mode")[1].lower()
        # Look for the autonomous-merge bullet and its ADR-029 citation.
        assert "autonomous merge" in must_stop_section
        assert "adr-029" in must_stop_section, "Must-stop gate must cite ADR-029"

    def test_conventions_author_checklist_enforces_merge_neutrality(self):
        """CONVENTIONS.md Author Checklist must enforce merge-neutral skills."""
        content = CONVENTIONS_MD.read_text()
        checklist_section = content.split("## Author Checklist")[1].lower()
        assert "autonomous-merge is fail-closed" in checklist_section
        assert "skills never instruct a pr merge" in checklist_section

    def test_aet_ship_states_human_merge_boundary(self):
        """aet-ship step 14 must state unambiguously that the human decides to merge."""
        content = AET_SHIP_SKILL.read_text()
        step_14 = content.split("14. **Merge Verification and Terminal Closure**")[1].lower()
        # The merge action is the human's decision, not the agent's.
        assert "human" in step_14
        assert "merge" in step_14
        assert "the pr merge is the human's decision" in step_14

    def test_aet_ship_has_no_self_merge_instruction(self):
        """aet-ship must not instruct an agent to run gh pr merge or self-merge."""
        content = AET_SHIP_SKILL.read_text()
        lower = content.lower()
        assert "gh pr merge" not in lower, "Skill must not instruct gh pr merge"
        # Reject explicit agent-directed self-merge directives.
        assert "self-merge" not in lower.replace("merge verification", "")
        assert "merge the pr" not in lower
        assert "merge your own pr" not in lower

    def test_aet_ship_key_principle_scopes_non_interactive_to_validation(self):
        """The 'Non-interactive by default' principle must scope to validation, not merge."""
        content = AET_SHIP_SKILL.read_text()
        principles = content.split("## Key Principles")[1]
        assert "Non-interactive by default" in principles
        assert "validation gate" in principles

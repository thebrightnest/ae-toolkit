"""Integration tests for the relative-link check in scripts/validate-skills.sh.

The validator derives its repo root from its own location
(``<repo>/scripts/validate-skills.sh``), so each test builds a minimal repo
in a temp dir — a copy of the script plus one fixture skill — and drives the
script via subprocess. These tests characterize the link-check behavior
(exit codes and messages) so the de-subshell refactor has a safety net.
"""

import shutil
import subprocess
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[2]
_SCRIPT_SOURCE = _REPO_ROOT / "scripts" / "validate-skills.sh"

_SKILL_MD = textwrap.dedent("""\
    ---
    name: demo-skill
    description: Demo skill for validator tests. Use when testing the validator.
    ---

    # Demo

    See the [reference](references/ref.md).
    """)


def _build_repo(tmp_path, skill_md, extra_files=None):
    """Materialize a minimal repo: validator copy plus one demo skill."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    shutil.copy(_SCRIPT_SOURCE, scripts_dir / "validate-skills.sh")
    skill = tmp_path / "demo-skill"
    (skill / "examples").mkdir(parents=True)
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(skill_md)
    for rel_path, content in (extra_files or {}).items():
        target = tmp_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return tmp_path


def _run_validator(repo):
    return subprocess.run(
        ["bash", str(repo / "scripts" / "validate-skills.sh")],
        capture_output=True,
        text=True,
        cwd=repo,
    )


def test_valid_relative_link_passes(tmp_path):
    repo = _build_repo(tmp_path, _SKILL_MD, {"demo-skill/references/ref.md": "# Ref\n"})
    result = _run_validator(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All skill structure checks passed" in result.stdout


def test_broken_relative_link_fails_and_names_file_and_link(tmp_path):
    repo = _build_repo(tmp_path, _SKILL_MD)  # ref.md deliberately absent
    result = _run_validator(repo)
    assert result.returncode != 0
    assert "Broken link in" in result.stdout
    assert "demo-skill/SKILL.md" in result.stdout
    assert "references/ref.md" in result.stdout


def test_code_block_http_and_anchor_links_are_skipped(tmp_path):
    skill_md = textwrap.dedent("""\
        ---
        name: demo-skill
        description: Demo skill for validator tests. Use when testing the validator.
        ---

        # Demo

        ```
        [broken-in-code](references/nope.md)
        ```

        See [external](https://example.com/docs) and the [anchor](#demo).
        """)
    repo = _build_repo(tmp_path, skill_md)
    result = _run_validator(repo)
    assert result.returncode == 0, result.stdout + result.stderr

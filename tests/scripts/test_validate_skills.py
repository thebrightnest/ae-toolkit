"""Integration tests for scripts/validate-skills.sh.

The validator derives its repo root from its own location
(``<repo>/scripts/validate-skills.sh``), so each test builds a minimal repo
in a temp dir — a copy of the script plus one fixture skill — and drives the
script via subprocess. These tests characterize the link-check and trigger-uniqueness behavior
(exit codes and messages) so the de-subshell refactors have a safety net.
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
    """Materialize a minimal repo: validator copy plus one demo skill under skills/."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    shutil.copy(_SCRIPT_SOURCE, scripts_dir / "validate-skills.sh")
    skill = tmp_path / "skills" / "demo-skill"
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
    repo = _build_repo(tmp_path, _SKILL_MD, {"skills/demo-skill/references/ref.md": "# Ref\n"})
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


def test_executable_code_in_skill_fails(tmp_path):
    """Skills must be content-only: .py files are rejected."""
    repo = _build_repo(
        tmp_path,
        _SKILL_MD,
        {"skills/demo-skill/examples/helper.py": "print('not allowed')\n"},
    )
    result = _run_validator(repo)
    assert result.returncode != 0
    assert "executable code" in result.stdout.lower()
    assert "helper.py" in result.stdout


_REF = {"skills/demo-skill/references/ref.md": "# Ref\n"}


def _second_skill(repo, name, description):
    """Add a second skill so trigger collisions have two claimants."""
    skill = repo / "skills" / name
    (skill / "examples").mkdir(parents=True)
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        textwrap.dedent(f"""\
            ---
            name: {name}
            description: {description}
            ---

            # {name}
            """)
    )


def test_two_skills_claiming_one_quoted_phrase_collide(tmp_path):
    repo = _build_repo(
        tmp_path,
        _SKILL_MD.replace(
            "Use when testing", 'Triggers on "shared phrase". Use when testing'
        ),
    )
    _second_skill(repo, "other-skill", 'Triggers on "shared phrase".')

    result = _run_validator(repo)

    assert result.returncode == 1, result.stdout
    assert "Trigger collision: 'shared phrase'" in result.stdout
    assert "demo-skill" in result.stdout
    assert "other-skill" in result.stdout


def test_distinct_quoted_phrases_do_not_collide(tmp_path):
    repo = _build_repo(
        tmp_path,
        _SKILL_MD.replace("Use when testing", 'Triggers on "mine". Use when testing'),
        extra_files=_REF,
    )
    _second_skill(repo, "other-skill", 'Triggers on "theirs".')

    result = _run_validator(repo)

    assert result.returncode == 0, result.stdout
    assert "No trigger collisions detected" in result.stdout


def test_phrase_matching_is_case_and_trailing_punctuation_insensitive(tmp_path):
    """Normalization: lowercased, one trailing punctuation mark stripped."""
    repo = _build_repo(
        tmp_path,
        _SKILL_MD.replace(
            "Use when testing", 'Triggers on "Shared Phrase." Use when testing'
        ),
    )
    _second_skill(repo, "other-skill", 'Triggers on "shared phrase".')

    result = _run_validator(repo)

    assert result.returncode == 1, result.stdout
    assert "Trigger collision: 'shared phrase'" in result.stdout


def test_a_two_character_phrase_is_ignored(tmp_path):
    """Too short to be a trigger; both skills may claim it."""
    repo = _build_repo(
        tmp_path,
        _SKILL_MD.replace("Use when testing", 'Triggers on "ab". Use when testing'),
        extra_files=_REF,
    )
    _second_skill(repo, "other-skill", 'Triggers on "ab".')

    result = _run_validator(repo)

    assert result.returncode == 0, result.stdout


def test_a_quoted_phrase_outside_the_frontmatter_is_not_a_trigger(tmp_path):
    """Only the description field declares triggers."""
    body_quote = _SKILL_MD.rstrip() + '\n\nThe body mentions "shared phrase" in prose.\n'
    repo = _build_repo(tmp_path, body_quote, extra_files=_REF)
    _second_skill(repo, "other-skill", 'Triggers on "shared phrase".')

    result = _run_validator(repo)

    assert result.returncode == 0, result.stdout

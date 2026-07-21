"""Merge-time lint for workflow-as-data files.

Validates the packaged ``src/aet/workflows/*.json`` and, when present, the
repo's ``.agents/workflows/*.json``. Reuses workflow.py's validation core so
the two cannot drift, then adds the merge-time-only check the runtime loader
deliberately skips: every bound skill must resolve to a
``<repo_root>/skills/<skill>/SKILL.md`` directory.

Output: one line per finding; exit 1 on any finding, exit 0 with a summary
line when green. Runtime tolerance for unknown extension keys is preserved —
the lint is the stricter merge-time judge, not a new runtime contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from aet import workflow as workflow_module


def lint_workflow_file(path: Path, repo_root: Path) -> list[str]:
    """Return lint findings for one workflow file (empty when clean)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: cannot read workflow: {exc}"]

    try:
        wf = workflow_module._parse_workflow(raw, path)
    except workflow_module.WorkflowError as exc:
        return [f"{path}: {exc}"]

    findings = []
    for stage in wf.stages:
        for skill in stage.skills:
            skill_md = repo_root / "skills" / skill / "SKILL.md"
            if not skill_md.is_file():
                findings.append(
                    f"{path}: stage {stage.name!r} binds unknown skill {skill!r} "
                    f"(expected {skill_md})"
                )
    return findings


def workflow_files(repo_root: Path) -> list[Path]:
    """Packaged workflow files plus any repo-level workflow files."""
    files = sorted(workflow_module._PACKAGED_DIR.glob("*.json"))
    repo_dir = repo_root / ".agents" / "workflows"
    if repo_dir.is_dir():
        files.extend(sorted(repo_dir.glob("*.json")))
    return files


def _run(repo_root: Path) -> int:
    files = workflow_files(repo_root)

    findings = []
    for path in files:
        findings.extend(lint_workflow_file(path, repo_root))

    for finding in findings:
        print(finding)
    if findings:
        print(f"✗ workflow lint: {len(findings)} finding(s) across {len(files)} file(s)")
        return 1
    print(f"✓ workflow lint: {len(files)} file(s) clean")
    return 0


app = typer.Typer(invoke_without_command=True)


@app.callback()
def validate_workflows(
    repo_root: str = typer.Option(
        ".",
        "--repo-root",
        help="Repository root used for skill resolution (default: cwd)",
    ),
) -> None:
    """Lint workflow-as-data files."""
    rc = _run(Path(repo_root).resolve())
    raise typer.Exit(rc)


def main(argv: list[str] | None = None) -> int:
    try:
        return app(argv or [], standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()

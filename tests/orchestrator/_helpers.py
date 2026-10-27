"""Shared helpers for orchestrator tests using the git-refs queue backend."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from aet.backends.git_refs_backend import GitRefsBackend
from aet.cli_adapter import CLIAdapter

QUEUE_BASENAME = "aet-queue"


def _ensure_git_repo(repo_root: str) -> None:
    """Initialize a git repo when the caller has not done so."""
    if (Path(repo_root) / ".git").exists():
        return
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.name", "Test User"],
        check=True,
    )


def queue_path(repo_root: str) -> str:
    """Return the canonical queue file path under ``repo_root``."""
    return str(Path(repo_root) / ".agents" / QUEUE_BASENAME)


def history_path(queue_file: str) -> str:
    """Return the canonical history JSONL path paired with ``queue_file``."""
    return str(Path(queue_file).with_name("work-history.jsonl"))


def write_queue(repo_root: str, tasks: list[dict]) -> str:
    """Seed ``tasks`` into the git-refs backend and return the queue path."""
    _ensure_git_repo(repo_root)
    queue_file = queue_path(repo_root)
    Path(queue_file).parent.mkdir(parents=True, exist_ok=True)
    backend = GitRefsBackend(
        queue_file=queue_file, history_file=history_path(queue_file)
    )
    backend.save(tasks)
    return queue_file


def load_queue(queue_file: str) -> list[dict]:
    """Load the live task queue from the git-refs backend."""
    backend = GitRefsBackend(
        queue_file=queue_file, history_file=history_path(queue_file)
    )
    return backend.load()["queue"]


_FAKE_AGENT = """#!{python}
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, {src!r})
from aet import evidence, telemetry

wt = os.environ.get("AET_WORKTREE") or os.getcwd()
name = os.environ.get("AET_TASK_ID") or pathlib.Path(wt).name
repo_root = os.environ.get("AET_REPO_ROOT") or str(pathlib.Path(wt).parents[1])
hook = pathlib.Path(repo_root, ".agents", "hooks", f"{{name}}.py")
if hook.exists():
    exec(hook.read_text(encoding="utf-8"), {{"wt": wt, "name": name, "repo_root": repo_root}})
pathlib.Path(wt, f"{{name}}.txt").write_text(name, encoding="utf-8")
subprocess.run(["git", "-C", wt, "add", "."], check=True)
subprocess.run(["git", "-C", wt, "commit", "-q", "-m", f"{{name}} work"], check=True)
record = {{
    "task_id": name,
    "stage": "qa-complete",
    "skill": "aet-qa",
    "verdict": "pass",
    "summary": "fake qa passed",
    "generated_at": telemetry.iso_now(),
    "tree_hash": "",
    "test_command": "true",
    "tests_total": 1,
    "tests_passed": 1,
    "tests_failed": 0,
}}
evidence.write_verdict(
    name, "qa", record, project_slug=telemetry.derive_project_slug(repo_root), worktree_dir=wt
)
"""

_TEST_WORKFLOW = {
    "version": 1,
    "name": "test",
    "done_state": "qa-complete",
    "stages": [
        {"name": "plan-approved", "skills": ["aet-implement"], "evidence": None, "gate_key": None},
        {"name": "implemented", "skills": ["aet-qa"], "evidence": "qa", "gate_key": None},
    ],
    "execution_policy": {"session_groups": [["plan-approved", "implemented"]]},
    "routing": {"default": {"harness": "claude", "model": None}, "by_stage": {}},
}


def install_fake_agent(bin_root: str):
    """Write a fake ``claude`` that commits one file and passes QA; return (bin_dir, adapter).

    A task runs ``.agents/hooks/<task-id>.py`` from the repo root first when it exists.
    """
    bin_dir = Path(bin_root, "fake-bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    agent = bin_dir / "claude"
    agent.write_text(
        _FAKE_AGENT.format(python=sys.executable, src=str(Path(__file__).parents[2] / "src")),
        encoding="utf-8",
    )
    agent.chmod(0o755)
    adapter = CLIAdapter(
        name="claude",
        bin="claude",
        prompt_flag="-p",
        workdir_flag=None,
        headless_flag="--dangerously-skip-permissions",
    )
    return bin_dir, adapter


def _git(repo_root: str, *args: str) -> None:
    subprocess.run(["git", "-C", repo_root, *args], check=True, capture_output=True)


def init_epic_repo(repo_root: str, origin_root: str, tasks: dict[str, str]) -> dict[str, str]:
    """Create a single-pr repo with a bare origin, one PRD and plan per task.

    Args:
        tasks: task id mapped to the PRD file stem it names.
    Returns:
        Task id mapped to its plan path.
    """
    subprocess.run(["git", "init", "--bare", "-q", origin_root], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", repo_root], check=True)
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test User")
    Path(repo_root, ".gitignore").write_text(".agents/hooks/\n", encoding="utf-8")
    agents = Path(repo_root, ".agents")
    (agents / "workflows").mkdir(parents=True, exist_ok=True)
    (agents / "workflows" / "test.json").write_text(json.dumps(_TEST_WORKFLOW), encoding="utf-8")
    (agents / "aet-config.json").write_text(
        json.dumps(
            {"trunk_branch": "main", "integration_mode": "single-pr", "validate_command": "true"}
        ),
        encoding="utf-8",
    )
    plans: dict[str, str] = {}
    for task_id, prd in tasks.items():
        prd_file = Path(repo_root, "docs", "prds", f"{prd}.md")
        prd_file.parent.mkdir(parents=True, exist_ok=True)
        prd_file.write_text(f"# {prd}\n", encoding="utf-8")
        plan = Path(repo_root, "docs", "plans", f"{task_id}.md")
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(
            f"---\nid: {task_id}\nworkflow: test\n---\n\n# {task_id}\n\n## Context\n\n"
            f"- PRD: `docs/prds/{prd}.md`\n\n_Stage: plan-approved_\n",
            encoding="utf-8",
        )
        plans[task_id] = str(plan)
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "initial")
    _git(repo_root, "remote", "add", "origin", origin_root)
    _git(repo_root, "push", "-q", "-u", "origin", "main")
    return plans

"""GitHub Issues backend for the aet-work queue."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from backends.base import TaskBackend
from queue import (
    LEGAL_TRANSITIONS,
    append_history,
    current_state,
    read_history,
    read_queue,
    write_queue,
)

DEFAULT_LABEL_PREFIX = "aet"

# Map canonical AET states to the label suffix used on GitHub.
STATE_LABELS: dict[str, str] = {
    "planned": "planned",
    "ready": "ready",
    "blocked": "blocked",
    "in_progress": "in-progress",
    "awaiting_merge": "awaiting-merge",
    "merged": "merged",
    "abandoned": "abandoned",
    "failed": "failed",
}

_LABEL_COLORS: dict[str, str] = {
    "planned": "808080",
    "ready": "0E8A16",
    "blocked": "B60205",
    "in_progress": "FBCA04",
    "awaiting_merge": "5319E7",
    "merged": "0052CC",
    "abandoned": "000000",
    "failed": "D93F0B",
}


class BackendError(RuntimeError):
    """Raised when a GitHub backend operation fails."""


class GitHubBackend(TaskBackend):
    """GitHub Issues adapter for the task backend interface.

    The local JSON queue remains the scheduling source of truth; this backend
    mirrors tasks as GitHub issues and AET states as issue labels.
    """

    def __init__(
        self,
        queue_file: str = ".agents/work-queue.json",
        history_file: str = ".agents/work-history.jsonl",
        repo: str = "",
        label_prefix: str = DEFAULT_LABEL_PREFIX,
        gh_path: str = "gh",
    ) -> None:
        self.queue_file = queue_file
        self.history_file = history_file
        self.repo = repo
        self.label_prefix = label_prefix
        self.gh_path = gh_path

    def load(self) -> dict[str, Any]:
        """Return queue and history from the local JSON mirror."""
        return {
            "queue": read_queue(self.queue_file),
            "history": read_history(self.history_file),
        }

    def save(
        self, queue: list[dict[str, Any]], wrapper: dict[str, Any] | None = None
    ) -> None:
        """Persist the queue to the local JSON mirror."""
        write_queue(self.queue_file, queue, wrapper=wrapper)

    def transition(
        self,
        task_id: str,
        from_state: str | None,
        to_state: str,
        by: str = "system",
        evidence: dict[str, Any] | None = None,
    ) -> bool:
        """Apply a validated state transition and update the issue label."""
        queue = read_queue(self.queue_file)
        task = next((t for t in queue if t.get("id") == task_id), None)
        if task is None:
            return False

        recorded_state = current_state(task)
        if recorded_state != from_state:
            return False

        legal = LEGAL_TRANSITIONS.get(from_state, set())
        if to_state not in legal:
            return False

        task["state"] = to_state
        append_history(task, from_state, to_state, by, evidence)
        write_queue(self.queue_file, queue)

        if to_state in {"merged", "abandoned"}:
            issue_number = task.get("github_issue_number")
            if issue_number is not None:
                self._close_issue(issue_number)
        else:
            self._update_issue_labels(task)
        return True

    def plan_drift(self, plans_dir: str | Path) -> list[str]:
        """Return plan files that are not present in queue or history."""
        data = self.load()
        queue = data["queue"]
        history = data["history"]

        queued_files = {t.get("plan_file") for t in queue if t.get("plan_file")}
        settled_files = {t.get("plan_file") for t in history if t.get("plan_file")}
        plan_files = sorted(Path(plans_dir).glob("*.md"))

        return [
            str(pf)
            for pf in plan_files
            if str(pf) not in queued_files and str(pf) not in settled_files
        ]

    def close(self) -> None:
        """No-op: the gh CLI processes are short-lived."""
        return

    def sync_task(self, task: dict[str, Any], is_new: bool) -> None:
        """Create a GitHub issue for a new task or update labels for an existing one."""
        if is_new:
            self._create_issue(task)
        else:
            self._update_issue_labels(task)

    def ensure_labels(self) -> None:
        """Ensure every required AET state label exists in the repository."""
        existing = {label["name"] for label in self._list_labels()}
        for state, suffix in STATE_LABELS.items():
            label = f"{self.label_prefix}:{suffix}"
            if label not in existing:
                self._create_label(label, state)

    # -------------------------------------------------------------------------
    # gh CLI helpers
    # -------------------------------------------------------------------------

    def _run_gh(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run a ``gh`` subcommand and return the completed process."""
        cmd = [self.gh_path, *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise BackendError(
                "GitHub CLI (gh) not found. Install it and run `gh auth login`."
            ) from exc

        if result.returncode != 0:
            raise BackendError(
                f"gh command failed ({result.returncode}): {result.stderr.strip()}"
            )
        return result

    def _list_labels(self) -> list[dict[str, Any]]:
        result = self._run_gh(
            ["label", "list", "--repo", self.repo, "--json", "name", "--limit", "1000"]
        )
        return json.loads(result.stdout or "[]")

    def _create_label(self, label: str, state: str) -> None:
        color = _LABEL_COLORS.get(state, "808080")
        self._run_gh(
            [
                "label",
                "create",
                "--repo",
                self.repo,
                label,
                "--color",
                color,
                "--description",
                f"AET state: {state}",
            ]
        )

    def _state_label(self, state: str | None) -> str:
        """Map an AET state to its GitHub label."""
        return f"{self.label_prefix}:{STATE_LABELS.get(state or 'planned', 'planned')}"

    def _create_issue(self, task: dict[str, Any]) -> None:
        """Create a GitHub issue for ``task`` and record its URL/number."""
        title = task.get("title") or task.get("id", "task")
        body = self._task_body(task)
        label = self._state_label(task.get("state"))

        result = self._run_gh(
            [
                "issue",
                "create",
                "--repo",
                self.repo,
                "--title",
                title,
                "--body",
                body,
                "--label",
                label,
            ]
        )
        url = result.stdout.strip()
        task["github_issue_url"] = url
        task["github_issue_number"] = int(url.rstrip("/").split("/")[-1])

    def _close_issue(self, issue_number: int) -> None:
        self._run_gh(["issue", "close", str(issue_number), "--repo", self.repo])

    def _set_issue_labels(
        self, issue_number: int, state: str, current_labels: list[str] | None = None
    ) -> None:
        """Ensure the issue has exactly the label for ``state``.

        If ``current_labels`` is provided, it is used to compute the diff;
        otherwise the issue is fetched first.
        """
        desired_label = self._state_label(state)
        if current_labels is None:
            result = self._run_gh(
                [
                    "issue",
                    "view",
                    str(issue_number),
                    "--repo",
                    self.repo,
                    "--json",
                    "labels",
                ]
            )
            data = json.loads(result.stdout)
            current_labels = [
                label["name"]
                for label in data.get("labels", [])
                if label["name"].startswith(f"{self.label_prefix}:")
            ]

        labels_to_add = [desired_label] if desired_label not in current_labels else []
        labels_to_remove = [label for label in current_labels if label != desired_label]

        if not labels_to_add and not labels_to_remove:
            return

        cmd = [
            "issue",
            "edit",
            str(issue_number),
            "--repo",
            self.repo,
        ]
        for label in labels_to_add:
            cmd.extend(["--add-label", label])
        for label in labels_to_remove:
            cmd.extend(["--remove-label", label])
        self._run_gh(cmd)

    def _update_issue_labels(self, task: dict[str, Any]) -> None:
        """Ensure the issue for ``task`` has exactly the label for its current state."""
        issue_number = task.get("github_issue_number")
        if issue_number is None:
            issue_number = self._find_issue_by_title(
                task.get("title") or task.get("id", "")
            )
            if issue_number is None:
                return
            task["github_issue_number"] = issue_number

        self._set_issue_labels(issue_number, task.get("state"))

    def _find_issue_by_title(self, title: str) -> int | None:
        """Find an open issue by title and return its number."""
        result = self._run_gh(
            [
                "issue",
                "list",
                "--repo",
                self.repo,
                "--state",
                "open",
                "--json",
                "number,title",
                "--search",
                title,
            ]
        )
        issues = json.loads(result.stdout or "[]")
        for issue in issues:
            if issue.get("title") == title:
                return issue["number"]
        return None

    def _task_body(self, task: dict[str, Any]) -> str:
        plan_file = task.get("plan_file")
        title = task.get("title", task.get("id", "task"))
        parts = [f"# {title}"]
        if plan_file:
            parts.append("")
            parts.append(f"Plan file: {plan_file}")
            parts.append("")
            parts.append(f"<!-- plan-file: {plan_file} -->")
        return "\n".join(parts)

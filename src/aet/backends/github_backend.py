"""GitHub Issues projection for the aet-work queue.

This is a one-way mirror, not a storage backend. The local JSON queue (or the
configured :class:`backends.base.TaskBackend`) remains the source of truth;
this projection creates and labels GitHub issues to reflect task state.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from aet.projections.base import Projection
from aet.queue import read_queue

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
    "quarantined": "quarantined",
    "draft": "draft",
    "backlog": "backlog",
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
    "quarantined": "D876E3",
    "draft": "C2E0C6",
    "backlog": "0052CC",
}


class BackendError(RuntimeError):
    """Raised when a GitHub projection operation fails."""


class GitHubBackend(Projection):
    """GitHub Issues projection for the aet-work queue.

    This class implements :class:`projections.base.Projection`. It no longer
    implements :class:`backends.base.TaskBackend`; storage is handled by the
    configured task backend (``json`` or ``git-refs``).
    """

    def __init__(
        self,
        queue_file: str = ".agents/work-queue.json",
        history_file: str = ".agents/work-history.jsonl",
        repo: str = "",
        label_prefix: str = DEFAULT_LABEL_PREFIX,
        gh_path: str = "gh",
        plans_dir: str = "docs/plans",
    ) -> None:
        self.queue_file = queue_file
        self.history_file = history_file
        self.repo = repo
        self.label_prefix = label_prefix
        self.gh_path = gh_path
        self.plans_dir = plans_dir
        self._labels_ensured = False

    def on_add(self, task: dict[str, Any], is_new: bool) -> None:
        """Create a GitHub issue for a new task or update labels for an existing one."""
        self._ensure_labels_once()
        if is_new:
            self._create_issue(task)
        else:
            self._update_issue_labels(task)

    def on_transition(
        self,
        task_id: str,
        from_state: str | None,
        to_state: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Mirror a non-terminal transition to the GitHub issue labels.

        Terminal states (``merged``/``abandoned``) are handled by
        ``on_close`` so the issue is closed rather than relabelled.
        """
        if to_state in {"merged", "abandoned"}:
            return
        self._ensure_labels_once()
        task = self._find_task(task_id)
        if task is None:
            return
        self._update_issue_labels(task, from_state=from_state)

    def on_close(
        self, task_id: str, evidence: dict[str, Any] | None = None
    ) -> None:
        """Close the GitHub issue for a terminal task, if one exists."""
        self._ensure_labels_once()
        task = self._find_task(task_id)
        if task is None:
            return
        issue_number = task.get("github_issue_number")
        if issue_number is None:
            issue_number = self._find_issue_by_id(task_id)
            if issue_number is None:
                return
        self._close_issue(issue_number)

    def ensure_labels(self) -> None:
        """Ensure every required AET state label exists in the repository."""
        existing = {label["name"] for label in self._list_labels()}
        for state, suffix in STATE_LABELS.items():
            label = f"{self.label_prefix}:{suffix}"
            if label not in existing:
                self._create_label(label, state)

    def reconcile(self, apply: bool = False) -> dict[str, Any]:
        """Heal drift between committed plans and GitHub Issues (R-17).

        Dry-run by default. With ``apply=True``, creates missing issues,
        corrects labels, and reopens hand-closed live issues. Orphan issues
        are reported and never deleted.
        """
        from aet.projections import reconcile as reconcile_helpers

        self._ensure_labels_once()
        live_tasks, live_ids = reconcile_helpers.load_tasks(
            self.plans_dir, self.queue_file, self.history_file
        )
        issues = self.list_issues(state="all")
        drift = reconcile_helpers.compute_drift(
            live_tasks,
            live_ids,
            issues,
            self.label_prefix,
            self._state_label,
            self._task_state,
        )

        if apply:
            for item in drift:
                self._apply_drift_item(item, live_tasks)

        return {
            "apply": apply,
            "live_plans": len(live_ids),
            "issues_scanned": len(issues),
            "drift": [self._drift_record(item) for item in drift],
        }

    def _apply_drift_item(self, item, live_tasks: dict[str, Any]) -> None:
        """Apply one corrective write for a drift item."""
        if item.drift_type == "missing":
            task = live_tasks[item.plan_id]
            self.on_add(task, is_new=True)
        elif item.drift_type == "closed-live":
            self._reopen_issue(item.issue_number)
            task = live_tasks[item.plan_id]
            self._set_issue_labels(
                item.issue_number,
                self._task_state(task),
                current_labels=item.actual_labels,
            )
        elif item.drift_type == "mislabeled":
            task = live_tasks[item.plan_id]
            self._set_issue_labels(
                item.issue_number,
                self._task_state(task),
                current_labels=item.actual_labels,
            )
        # orphan: report only, never delete

    @staticmethod
    def _drift_record(item) -> dict[str, Any]:
        """Return a JSON-serializable drift record."""
        record: dict[str, Any] = {
            "type": item.drift_type,
            "plan_id": item.plan_id,
        }
        if item.issue_number is not None:
            record["issue_number"] = item.issue_number
        if item.expected_label is not None:
            record["expected_label"] = item.expected_label
        if item.actual_labels is not None:
            record["actual_labels"] = item.actual_labels
        return record

    def _ensure_labels_once(self) -> None:
        """Provision labels the first time the projection is used."""
        if not self._labels_ensured:
            self.ensure_labels()
            self._labels_ensured = True

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

    def _task_state(self, task: dict[str, Any]) -> str:
        """Map a task to the label key that reflects its current projection.

        Pre-sprint plan status drives the label; in-sprint queue state drives it
        once the task has been queued.
        """
        status = task.get("status")
        if status == "draft":
            return "draft"
        if status in {"approved", "backlog"}:
            return "backlog"
        return task.get("state") or "planned"

    def _state_label(self, state: str | None) -> str:
        """Map an AET state to its GitHub label."""
        return f"{self.label_prefix}:{STATE_LABELS.get(state or 'planned', 'planned')}"

    def _create_issue(self, task: dict[str, Any]) -> None:
        """Create a GitHub issue for ``task`` and record its URL/number.

        Creation is idempotent by plan id: if an issue already exists for this
        task, the issue is reconciled to the current label instead of creating a
        duplicate. This makes ``aet backlog add`` safe to re-run and safe across
        clones (R-10, R-13).
        """
        task_id = task.get("id", "task")
        existing_number = self._find_issue_by_id(task_id)
        if existing_number is not None:
            task["github_issue_number"] = existing_number
            self._update_issue_labels(task)
            return

        title = task.get("title") or task_id
        body = self._task_body(task)
        label = self._state_label(self._task_state(task))

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

    def _reopen_issue(self, issue_number: int) -> None:
        self._run_gh(["issue", "reopen", str(issue_number), "--repo", self.repo])

    def list_issues(self, state: str = "all") -> list[dict[str, Any]]:
        """Return issues with their labels and bodies.

        The result is normalized so ``labels`` is a list of label names.
        """
        result = self._run_gh(
            [
                "issue",
                "list",
                "--repo",
                self.repo,
                "--state",
                state,
                "--json",
                "number,labels,body,state",
                "--limit",
                "1000",
            ]
        )
        issues = json.loads(result.stdout or "[]")
        for issue in issues:
            issue["labels"] = [
                label["name"]
                for label in issue.get("labels", [])
                if isinstance(label, dict)
            ]
        return issues

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

    def _update_issue_labels(
        self, task: dict[str, Any], from_state: str | None = None
    ) -> None:
        """Ensure the issue for ``task`` has exactly the label for its projection."""
        issue_number = task.get("github_issue_number")
        if issue_number is None:
            issue_number = self._find_issue_by_id(task.get("id", ""))
            if issue_number is None:
                return
            task["github_issue_number"] = issue_number

        current_labels = None
        if from_state is not None:
            current_labels = [self._state_label(from_state)]
        self._set_issue_labels(
            issue_number, self._task_state(task), current_labels=current_labels
        )

    def _find_task(self, task_id: str) -> dict[str, Any] | None:
        """Return the queue entry for ``task_id`` from the local mirror, or None."""
        queue = read_queue(self.queue_file)
        return next((t for t in queue if t.get("id") == task_id), None)

    def _find_issue_by_id(self, task_id: str) -> int | None:
        """Find an open issue by its embedded ``aet-id`` marker."""
        result = self._run_gh(
            [
                "issue",
                "list",
                "--repo",
                self.repo,
                "--state",
                "open",
                "--json",
                "number,body",
                "--search",
                f"aet-id: {task_id}",
            ]
        )
        issues = json.loads(result.stdout or "[]")
        marker = f"<!-- aet-id: {task_id} -->"
        for issue in issues:
            if marker in (issue.get("body") or ""):
                return issue["number"]
        return None

    def _task_body(self, task: dict[str, Any]) -> str:
        plan_file = task.get("plan_file")
        title = task.get("title", task.get("id", "task"))
        task_id = task.get("id", "task")
        parts = [f"# {title}"]
        if plan_file:
            parts.append("")
            parts.append(f"Plan file: {plan_file}")
            parts.append("")
            parts.append(f"<!-- plan-file: {plan_file} -->")
        parts.append("")
        parts.append(f"<!-- aet-id: {task_id} -->")
        return "\n".join(parts)

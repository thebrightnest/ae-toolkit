"""Fail-open projection dispatcher for aet-work.

A projection is a one-way mirror. The dispatcher fans out each lifecycle event
to every configured projection and swallows any exception with a stderr warning.
Storage writes remain fail-closed: this module never catches exceptions raised
by a :class:`backends.base.TaskBackend`.
"""

from __future__ import annotations

import sys
from typing import Any

from aet.projections.base import Projection


class ProjectionDispatcher:
    """Fan out task lifecycle events to projections, swallowing projection failures.

    The dispatcher is the single place that enforces the fail-open rule for
    projections. Individual projections raise normally; the dispatcher catches
    and warns so the accompanying storage write always proceeds.
    """

    def __init__(self, projections: list[Projection]) -> None:
        self.projections = list(projections)

    def on_add(self, task: dict[str, Any], is_new: bool) -> None:
        self._call_each("on_add", task, is_new)

    def on_transition(
        self,
        task_id: str,
        from_state: str | None,
        to_state: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        self._call_each(
            "on_transition", task_id, from_state, to_state, evidence=evidence
        )

    def on_close(
        self, task_id: str, evidence: dict[str, Any] | None = None
    ) -> None:
        self._call_each("on_close", task_id, evidence=evidence)

    def ensure_labels(self) -> None:
        self._call_each("ensure_labels")

    def reconcile(self, apply: bool = False) -> list[dict[str, Any] | None]:
        """Fan out reconcile to every projection and collect their reports."""
        results: list[dict[str, Any] | None] = []
        for projection in self.projections:
            name = type(projection).__name__
            try:
                method = getattr(projection, "reconcile")
                results.append(method(apply=apply))
            except Exception as exc:  # noqa: BLE001 - fail-open is the contract
                print(
                    f"warning: projection {name} failed during reconcile: {exc}",
                    file=sys.stderr,
                )
                results.append(None)
        return results

    def _call_each(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        for projection in self.projections:
            name = type(projection).__name__
            try:
                method = getattr(projection, method_name)
                method(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - fail-open is the contract
                print(
                    f"warning: projection {name} failed during {method_name}: {exc}",
                    file=sys.stderr,
                )


def resolve_projections(config: dict[str, Any]) -> ProjectionDispatcher:
    """Build a dispatcher from the resolved AET config.

    The caller is responsible for external-first resolution; this function
    accepts the resolved config dict and reads the ``projections`` key.
    """
    projections: list[Projection] = []
    for entry in config.get("projections", []):
        ptype = entry.get("type")
        if ptype == "github":
            from aet.backends.github_backend import GitHubBackend

            repo = entry.get("repo") or config.get("github", {}).get("repo", "")
            label_prefix = (
                entry.get("label_prefix")
                or config.get("github", {}).get("label_prefix", "aet")
            )
            projections.append(
                GitHubBackend(repo=repo, label_prefix=label_prefix)
            )
    return ProjectionDispatcher(projections)

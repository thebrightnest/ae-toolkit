"""aet-work metrics — Cross-task metrics over settled history.

Prints the canonical ``metrics.aggregate`` projection: first-pass merge rate,
rework, and cost per merged task, overall and per work class. An empty or
missing history is a valid state (rc 0), not an error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import metrics  # noqa: E402


def _fmt_rate(bucket: dict) -> str:
    rate = bucket["first_pass_rate"]
    if rate is None:
        return "- (no merged tasks)"
    return f"{rate * 100:.1f}% ({bucket['first_pass']}/{bucket['merged']} merged)"


def _fmt_rework(bucket: dict) -> str:
    return str(bucket["rework"])


def _fmt_cost(bucket: dict) -> str:
    cost = bucket["cost"]
    tokens = cost["tokens_avg_per_merged"]
    usd = cost["usd_avg_per_merged"]
    tokens_s = f"{tokens:.0f} tokens" if tokens is not None else "-"
    usd_s = f"${usd:.4f}" if usd is not None else "-"
    return f"{tokens_s} / {usd_s} usd ({cost['usd_known_tasks']} known)"


def _render_section(title: str, projection: dict, fmt) -> list[str]:
    lines = [title]
    rows = [("overall", projection["overall"])]
    rows.extend(projection["classes"].items())
    width = max(len(name) for name, _ in rows)
    for name, bucket in rows:
        lines.append(f"  {name.ljust(width)}  {fmt(bucket)}")
    return lines


def _render_human(projection: dict) -> str:
    lines = ["Metrics over settled tasks", ""]
    for title, fmt in (
        ("First-pass merge rate", _fmt_rate),
        ("Rework", _fmt_rework),
        ("Cost per merged task", _fmt_cost),
    ):
        lines.extend(_render_section(title, projection, fmt))
        lines.append("")
    return "\n".join(lines).rstrip()


app = typer.Typer(invoke_without_command=True)


@app.callback()
def metrics_cmd(
    history_file: str = typer.Option(
        ".agents/work-history.jsonl",
        "--history-file",
        help="Path to work-history.jsonl",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        help="Only include tasks settled on or after this date (YYYY-MM-DD)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print the machine-readable projection instead of the human report",
    ),
) -> None:
    """Report cross-task metrics over settled history."""
    if since is not None:
        try:
            metrics._parse_date(since)
        except ValueError:
            print(
                f"⛔ invalid --since '{since}' (expected YYYY-MM-DD)",
                file=sys.stderr,
            )
            raise typer.Exit(1)
    projection = metrics.aggregate(history_file, since=since)
    if json_output:
        print(json.dumps(projection, indent=2))
        raise typer.Exit(0)
    if projection["overall"]["settled"] == 0:
        print("No settled tasks found in the selected window.")
        raise typer.Exit(0)
    print(_render_human(projection))
    raise typer.Exit(0)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        return app(argv, standalone_mode=False)
    except (
        click.exceptions.ClickException,
        typer._click.exceptions.ClickException,
    ) as exc:
        exc.show()
        return exc.exit_code
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()

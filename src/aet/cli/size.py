"""aet size — Delivered-size measurement loop commands.

Provides ``aet size report`` for the delivered-size distribution by declared
label and ``aet size backfill`` for idempotently measuring historical records.
"""

from __future__ import annotations

import json
import sys

import click
import typer

from aet import metrics

app = typer.Typer(no_args_is_help=True)


def _render_report(projection: dict) -> str:
    lines = ["Delivered size by declared label", ""]
    lines.append(f"{'Label':<6} {'n':>4} {'median':>8} {'p90':>8} {'exceeds band':>12}")
    for label in ("S", "M", "L"):
        bucket = projection["labels"][label]
        n = bucket["n"]
        if n == 0:
            row = f"{label:<6} {n:>4} {'-':>8} {'-':>8} {'-':>12}"
        else:
            median = f"{bucket['median']:.0f}"
            p90 = f"{bucket['p90']:.0f}"
            exceeds = f"{bucket['exceeds_band'] * 100:.0f}%"
            row = f"{label:<6} {n:>4} {median:>8} {p90:>8} {exceeds:>12}"
        lines.append(row)
    lines.append("")
    lines.append(f"Sample size: {projection['sample_size']} tasks with a measured delivered_size.")
    lines.append(
        "Caveats: distribution is over historical delivery; small samples are noisy; "
        "L has no upper band so 'exceeds band' is always 0%."
    )
    return "\n".join(lines)


def _render_backfill(result: dict) -> str:
    lines = [
        "Backfill complete",
        f"  measured:      {result['measured']}",
        f"  skipped:       {result['skipped']}",
        f"  unresolvable:  {result['unresolvable']}",
    ]
    if result["reasons"]:
        lines.append("Unresolvable reasons:")
        for reason, count in sorted(result["reasons"].items()):
            lines.append(f"  - {reason}: {count}")
    return "\n".join(lines)


@app.callback()
def size_cmd() -> None:
    """Delivered-size measurement and reporting."""


@app.command("report")
def report_cmd(
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
    """Report delivered size by declared S/M/L label."""
    if since is not None:
        try:
            metrics._parse_date(since)
        except ValueError:
            print(
                f"⛔ invalid --since '{since}' (expected YYYY-MM-DD)",
                file=sys.stderr,
            )
            raise typer.Exit(1)

    projection = metrics.aggregate_delivered_size(history_file, since=since)
    if json_output:
        print(json.dumps(projection, indent=2))
        raise typer.Exit(0)

    if projection["sample_size"] == 0:
        print("No measured delivered_size records found in the selected window.")
        raise typer.Exit(0)

    print(_render_report(projection))
    raise typer.Exit(0)


@app.command("backfill")
def backfill_cmd(
    history_file: str = typer.Option(
        ".agents/work-history.jsonl",
        "--history-file",
        help="Path to work-history.jsonl",
    ),
    repo_root: str = typer.Option(
        ".",
        "--repo-root",
        help="Repository root for resolving plan files and merge commits",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print the machine-readable result instead of the human summary",
    ),
    min_yield: int | None = typer.Option(
        None,
        "--min-yield",
        help="Minimum number of newly measured records required for success",
    ),
) -> None:
    """Backfill delivered_size for settled history records."""
    result = metrics.backfill_delivered_size(history_file, repo_root)

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(_render_backfill(result))

    if min_yield is not None and result["measured"] < min_yield:
        print(
            f"⛔ backfill yield {result['measured']} is below required minimum {min_yield}",
            file=sys.stderr,
        )
        raise typer.Exit(1)

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

#!/usr/bin/env python3
"""Serve the AET telemetry panel together with ~/.aet/telemetry.

Opens the panel in your default browser; the page reads the archive through
a tiny localhost-only JSON API backed by Starlette + uvicorn.

Usage:
    aet panel                               # serve + open browser
    aet panel --no-open                     # serve only, print the URL
    python3 -m aet.panel.serve --no-open    # direct module invocation
"""

import os
import socket
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

TELEMETRY = os.path.expanduser("~/.aet/telemetry")
PANEL_DIR = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"


def telemetry_files():
    """Relative paths of all telemetry files in the archive."""
    out = []
    if not os.path.isdir(TELEMETRY):
        return out
    for root, _dirs, files in os.walk(TELEMETRY):
        for name in files:
            if name == "last-run.json" or (
                name.endswith(".jsonl") and name != "work-history.jsonl"
            ):
                out.append(os.path.relpath(os.path.join(root, name), TELEMETRY))
    return sorted(out)


def _is_date_segment(name):
    """True for YYYY-MM-DD archive path segments (same rule as telemetry.py)."""
    try:
        datetime.strptime(name, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _newest_mtime(path):
    """Newest mtime within path, including the dir itself.

    Same definition as telemetry.py:_newest_mtime — the aggregate prune
    safety already trusts — so JSONL appends count as run activity.
    """
    newest = path.stat().st_mtime
    for entry in path.rglob("*"):
        try:
            newest = max(newest, entry.stat().st_mtime)
        except OSError:
            continue
    return newest


def run_dirs():
    """Current-layout run dirs ({project}/{YYYY-MM-DD}/{run-id}) with activity.

    A dir is a run dir when its parent's basename parses as a date (mirrors
    telemetry.py:_iter_project_run_dirs; legacy {date}-{run-id} dirs fail the
    date check and are excluded). Symlinked dirs are skipped, as in the prune
    walk. mtime is the newest recursive mtime, so appends register. Empty
    run dirs are included — that is the point (lvp-01).
    """
    out = []
    if not os.path.isdir(TELEMETRY):
        return out
    for root, dirnames, _files in os.walk(TELEMETRY):
        if not _is_date_segment(os.path.basename(root)):
            continue
        for name in sorted(dirnames):
            full = os.path.join(root, name)
            if os.path.islink(full):
                continue
            out.append(
                {"rel": os.path.relpath(full, TELEMETRY), "mtime": _newest_mtime(Path(full))}
            )
        dirnames[:] = []  # run dirs never nest run dirs; stop descending
    return sorted(out, key=lambda d: d["rel"])


async def index(request: Request):
    """Serve the bundled HTML panel."""
    return FileResponse(
        os.path.join(PANEL_DIR, "index.html"),
        media_type="text/html; charset=utf-8",
    )


async def api_list(request: Request):
    """Return archive metadata: root path, files, and run directories."""
    return JSONResponse(
        {"root": TELEMETRY, "files": telemetry_files(), "dirs": run_dirs()}
    )


async def api_file(request: Request):
    """Serve a single archive file by relative path, rejecting traversal."""
    rel = request.query_params.get("p", "")
    full = os.path.normpath(os.path.join(TELEMETRY, rel))
    if os.path.commonpath([TELEMETRY, full]) != TELEMETRY or not os.path.isfile(full):
        return PlainTextResponse("not found", status_code=404)
    return FileResponse(full, media_type="application/json")


async def favicon(request: Request):
    """Quietly 204 on favicon requests."""
    return Response(status_code=204)


async def not_found(request: Request):
    """Fallback 404 for unmatched routes."""
    return PlainTextResponse("not found", status_code=404)


app = Starlette(
    routes=[
        Route("/", index),
        Route("/index.html", index),
        Route("/api/list", api_list),
        Route("/api/file", api_file),
        Route("/favicon.ico", favicon),
    ],
    exception_handlers={404: not_found},
)


def _bound_socket():
    """Return a TCP socket bound to the loopback interface on a random port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, 0))
    sock.listen(128)
    return sock


def main():
    sock = _bound_socket()
    try:
        _host, port = sock.getsockname()[:2]
        url = f"http://{HOST}:{port}/"
        print(f"AET telemetry panel: {url}")
        print(f"Archive: {TELEMETRY}")
        print("Press Ctrl-C to stop.")
        if "--no-open" not in sys.argv:
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()

        config = uvicorn.Config(
            app,
            host=HOST,
            fd=sock.fileno(),
            log_level="warning",
            access_log=False,
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        try:
            server.run()
        finally:
            print("\nstopped")
    finally:
        sock.close()


if __name__ == "__main__":
    main()

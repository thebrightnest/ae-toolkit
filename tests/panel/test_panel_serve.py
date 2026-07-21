"""Tests for aet.panel.serve — the panel HTTP surface (R-9).

The panel server is a Starlette application bound to 127.0.0.1 only. Tests
exercise it through real HTTP requests against a uvicorn server running in a
thread against a tmp archive.
"""

import asyncio
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import uvicorn

from aet.panel import serve

REPO_ROOT = Path(__file__).parents[2]
PANEL_DIR = REPO_ROOT / "src" / "aet" / "panel"


def _start_server(app, archive):
    """Run uvicorn in a daemon thread; return (server, url)."""
    serve.TELEMETRY = str(archive)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=0,
        log_level="warning",
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(100):
        if server.started and getattr(server, "servers", None):
            sock = server.servers[0].sockets[0]
            port = sock.getsockname()[1]
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("panel server did not start")

    return server, f"http://127.0.0.1:{port}"


def _stop_server(server):
    """Signal uvicorn to shut down and wait for the thread."""
    if not getattr(server, "servers", None):
        return
    loop = server.servers[0].get_loop()
    future = asyncio.run_coroutine_threadsafe(server.shutdown(), loop)
    future.result(timeout=5)


@pytest.fixture
def panel_server(tmp_path):
    """Run the real panel server against a tmp archive; yield (url, archive)."""
    archive = tmp_path / "telemetry"
    archive.mkdir()
    original_telemetry = serve.TELEMETRY
    server, url = _start_server(serve.app, archive)
    try:
        yield url, archive
    finally:
        _stop_server(server)
        serve.TELEMETRY = original_telemetry


def _get(url):
    with urllib.request.urlopen(url) as res:
        return res.status, res.read(), res.headers


def _get_json(url):
    status, data, _headers = _get(url)
    return status, json.loads(data)


def _run_dir(archive, project, date, run_id):
    d = archive / project / date / run_id
    d.mkdir(parents=True)
    return d


def test_index_html_served(panel_server):
    """The root and /index.html paths return the bundled HTML page."""
    url, _archive = panel_server
    for path in ("/", "/index.html"):
        status, data, headers = _get(url + path)
        assert status == 200
        assert b"AET Telemetry Panel" in data
        assert headers.get("Content-Type") == "text/html; charset=utf-8"


def test_dirs_includes_all_current_layout_run_dirs(panel_server):
    """Empty, partial, and completed current-layout run dirs all appear in dirs."""
    url, archive = panel_server
    _run_dir(archive, "proj", "2026-07-13", "run-empty")
    partial = _run_dir(archive, "proj", "2026-07-13", "run-partial")
    (partial / "task.jsonl").write_text('{"type":"stage"}\n')
    done = _run_dir(archive, "proj", "2026-07-12", "run-done")
    (done / "task.jsonl").write_text('{"type":"stage"}\n')
    (done / "last-run.json").write_text('{"outcome":"success"}')

    status, body = _get_json(url + "/api/list")

    assert status == 200
    rels = {d["rel"] for d in body["dirs"]}
    assert rels == {
        "proj/2026-07-13/run-empty",
        "proj/2026-07-13/run-partial",
        "proj/2026-07-12/run-done",
    }


def test_dirs_excludes_legacy_run_dir(panel_server):
    """Legacy {date}-{run-id} dirs predate this feature; the panel sees their files."""
    url, archive = panel_server
    legacy = archive / "proj" / "2026-07-01-abc123"
    legacy.mkdir(parents=True)
    (legacy / "execution.log.jsonl").write_text("{}\n")
    _run_dir(archive, "proj", "2026-07-02", "run-current")

    _, body = _get_json(url + "/api/list")

    assert [d["rel"] for d in body["dirs"]] == ["proj/2026-07-02/run-current"]


def test_dirs_excludes_non_date_parent(panel_server):
    """A dir whose parent is not a YYYY-MM-DD segment is not a run dir."""
    url, archive = panel_server
    (archive / "proj" / "not-a-date" / "run-x").mkdir(parents=True)

    _, body = _get_json(url + "/api/list")

    assert body["dirs"] == []


def test_dirs_mtime_tracks_newest_file(panel_server):
    """mtime is the newest recursive mtime: a JSONL append advances it even
    though appends do not touch the directory's own mtime."""
    url, archive = panel_server
    run = _run_dir(archive, "proj", "2026-07-13", "run-mtime")
    log = run / "task.jsonl"
    log.write_text('{"type":"stage"}\n')
    old = 1_700_000_000.0
    os.utime(log, (old, old))
    os.utime(run, (old, old))

    _, body = _get_json(url + "/api/list")
    assert body["dirs"][0]["mtime"] == old

    with open(log, "a") as f:
        f.write('{"type":"test_run"}\n')
    newer = old + 120
    os.utime(log, (newer, newer))

    _, body = _get_json(url + "/api/list")
    assert body["dirs"][0]["mtime"] == newer


def test_files_listing_unchanged(panel_server):
    """Regression: the files array keeps today's shape — last-run.json plus
    JSONL files, excluding work-history.jsonl and non-telemetry files."""
    url, archive = panel_server
    run = _run_dir(archive, "proj", "2026-07-13", "run-files")
    (run / "task.jsonl").write_text("{}\n")
    (run / "last-run.json").write_text("{}")
    (run / "work-history.jsonl").write_text("{}\n")
    (run / "notes.txt").write_text("nope")

    _, body = _get_json(url + "/api/list")

    assert body["files"] == [
        "proj/2026-07-13/run-files/last-run.json",
        "proj/2026-07-13/run-files/task.jsonl",
    ]


def test_api_file_serves_json_file(panel_server):
    """Regression: /api/file returns the requested archive file."""
    url, archive = panel_server
    run = _run_dir(archive, "proj", "2026-07-13", "run-file")
    (run / "task.jsonl").write_text('{"type":"stage"}\n')

    status, data, headers = _get(url + "/api/file?p=proj/2026-07-13/run-file/task.jsonl")

    assert status == 200
    assert json.loads(data) == {"type": "stage"}
    assert headers.get("Content-Type") == "application/json"


def test_api_file_rejects_traversal(panel_server):
    """Regression: /api/file still 404s on `..` escaping the archive root."""
    url, archive = panel_server
    (archive.parent / "secret.txt").write_text("nope")

    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(url + "/api/file?p=../secret.txt")

    assert exc.value.code == 404


def test_favicon_204(panel_server):
    """/favicon.ico returns a quiet 204 No Content."""
    url, _archive = panel_server
    req = urllib.request.Request(url + "/favicon.ico", method="GET")
    with urllib.request.urlopen(req) as res:
        assert res.status == 204


def test_server_binds_loopback_only():
    """The panel server refuses to bind on a non-loopback address."""
    # Reaching outside 127.0.0.1 is a security regression; ensure the binding
    # helper is hard-coded to loopback.
    assert serve.HOST == "127.0.0.1"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Binding to 0.0.0.0 should fail if serve.HOST were "0.0.0.0"? Not directly.
    # Instead, verify the helper returns a socket bound to 127.0.0.1.
    bound = serve._bound_socket()
    try:
        assert bound.getsockname()[0] == "127.0.0.1"
    finally:
        bound.close()

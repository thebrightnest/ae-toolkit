"""Tests for aet-work/panel/serve — the /api/list dirs payload (lvp-01).

The panel server is an extensionless stdlib script; load it via importlib and
exercise it through its public interface: real HTTP requests against a
ThreadingHTTPServer bound to a tmp archive.
"""

import importlib.machinery
import importlib.util
import json
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SERVE_PATH = REPO_ROOT / "aet-work" / "panel" / "serve"


def _load_serve():
    loader = importlib.machinery.SourceFileLoader("panel_serve", str(SERVE_PATH))
    spec = importlib.util.spec_from_loader("panel_serve", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def panel_server(tmp_path):
    """Run the real panel server against a tmp archive; yield (url, archive)."""
    serve = _load_serve()
    archive = tmp_path / "telemetry"
    archive.mkdir()
    serve.TELEMETRY = str(archive)
    server = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", archive
    server.shutdown()


def _get_json(url):
    with urllib.request.urlopen(url) as res:
        return res.status, json.loads(res.read())


def _run_dir(archive, project, date, run_id):
    d = archive / project / date / run_id
    d.mkdir(parents=True)
    return d


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


def test_api_file_rejects_traversal(panel_server):
    """Regression: /api/file still 404s on `..` escaping the archive root."""
    url, archive = panel_server
    (archive.parent / "secret.txt").write_text("nope")

    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(url + "/api/file?p=../secret.txt")

    assert exc.value.code == 404

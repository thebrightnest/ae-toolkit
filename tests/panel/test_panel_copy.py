"""The panel's user-facing copy must not name the retired `aet-work` skill."""

from __future__ import annotations

from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "src" / "aet" / "panel" / "index.html"


def test_panel_copy_does_not_name_aet_work():
    assert ">aet-work</code>" not in INDEX_HTML.read_text(encoding="utf-8")


def test_panel_copy_names_aet_run():
    assert ">aet run</code>" in INDEX_HTML.read_text(encoding="utf-8")

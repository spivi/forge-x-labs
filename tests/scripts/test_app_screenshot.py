"""Tests for scripts/app_screenshot.py -- the generic vis-UI gate.

The gate decision, slug, port, and path helpers are pure + tested directly. The
browser/process driver is fail-soft and excluded from coverage.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("app_screenshot", _SCRIPTS / "app_screenshot.py")
aps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aps)


# --- should_gate ----------------------------------------------------------


def test_gate_fires_when_on_and_ui_labeled():
    assert aps.should_gate("effort:M;area:ui", vis_ui_mode="on") is True


def test_gate_skipped_when_off():
    assert aps.should_gate("area:ui", vis_ui_mode="off") is False


def test_gate_skipped_without_ui_label():
    assert aps.should_gate("effort:M;area:api", vis_ui_mode="on") is False


def test_gate_default_reads_project_conf_off():
    # No injected mode -> reads project.conf VIS_UI_GATE (ships off) -> never fires.
    assert aps.should_gate("area:ui") is False


# --- slug / paths / port --------------------------------------------------


def test_slug_root_and_nested():
    assert aps.slug("/") == "root"
    assert aps.slug("/dashboard") == "dashboard"
    assert aps.slug("/a/b") == "a-b"
    assert aps.slug("/search?q=1") == "search-q-1"


def test_out_path_uses_slug_and_short_sha(tmp_path):
    p = aps.out_path(tmp_path, "/dashboard", "abcdef1234567")
    assert p.name == "dashboard-abcdef1.png"
    assert p.parent == tmp_path


def test_out_path_local_when_no_sha(tmp_path):
    assert aps.out_path(tmp_path, "/", "").name == "root-local.png"


def test_free_port_is_int_in_range():
    port = aps.free_port()
    assert isinstance(port, int)
    assert 1024 < port < 65536

#!/usr/bin/env python3
"""Generic vis-UI screenshot gate (advisory).

Boots the app, waits for health, and screenshots a set of routes so a reviewer can
eyeball UI acceptance criteria before merge. Fully generic + config-driven — no
framework specifics. Off by default; fires only when `VIS_UI_GATE=on` in project.conf
AND the ticket carries a generic `area:ui` label. Advisory: a screenshot failure is
surfaced to the human, it never hard-blocks a merge.

The decision (`should_gate`), the filesystem-safe `slug`, and `free_port` are pure +
unit-tested. The browser driver requires Playwright (`pip install playwright &&
playwright install chromium`) and is fail-soft: absent Playwright => a logged skip,
not a crash.

CLI:
    python scripts/app_screenshot.py --start-cmd "uvicorn app.main:app --port {port}" \
        --health-url "http://127.0.0.1:{port}/health" --routes / /dashboard \
        --base-url "http://127.0.0.1:{port}" --sha <sha>
"""

from __future__ import annotations

import argparse
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
_PROJECT_CONF = PROJECT_DIR / ".dev-context" / "project.conf"
DEFAULT_OUT_DIR = PROJECT_DIR / "docs" / "ui-screenshots"


# --- pure decision logic --------------------------------------------------


def _conf(key: str, default: str = "") -> str:
    if not _PROJECT_CONF.exists():
        return default
    for line in _PROJECT_CONF.read_text().splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return default


def should_gate(labels: str, *, vis_ui_mode: str | None = None, ui_label: str = "area:ui") -> bool:
    """The gate fires only when VIS_UI_GATE is on AND the ticket carries `area:ui`.
    `labels` is the ticket's label string/row value; `vis_ui_mode` defaults to the
    project.conf VIS_UI_GATE value."""
    mode = (
        (vis_ui_mode if vis_ui_mode is not None else _conf("VIS_UI_GATE", "off")).strip().lower()
    )
    if mode not in ("on", "true", "1"):
        return False
    return ui_label in (labels or "")


def slug(route: str) -> str:
    """Filesystem-safe slug for a route ('/' -> 'root', '/a/b?x=1' -> 'a-b-x-1')."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", route.strip("/")).strip("-").lower()
    return cleaned or "root"


def free_port() -> int:
    """An OS-assigned free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def out_path(out_dir: Path, route: str, sha: str) -> Path:
    """Screenshot path: <out_dir>/<route-slug>-<sha7>.png."""
    return Path(out_dir) / f"{slug(route)}-{(sha or 'local')[:7]}.png"


# --- runtime (network/browser; fail-soft) ---------------------------------


def wait_for_url(url: str, timeout_s: float = 30.0) -> bool:  # pragma: no cover (network)
    """Poll `url` until it responds (any HTTP status) or timeout. True if reachable."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)  # noqa: S310
            return True
        except urllib.error.HTTPError:
            return True  # got a response, app is up
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    return False


def screenshot_routes(
    base_url: str, routes: list[str], out_dir: Path, sha: str
) -> list[Path]:  # pragma: no cover (browser)
    """Screenshot each route via Playwright. Fail-soft: returns [] (with a logged
    hint) if Playwright is not installed."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        print(
            "app_screenshot: Playwright not installed — skipping vis-UI gate. "
            "Enable with `pip install playwright && playwright install chromium`.",
            file=sys.stderr,
        )
        return []
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for route in routes:
            target = out_path(out_dir, route, sha)
            page.goto(base_url.rstrip("/") + "/" + route.lstrip("/"))
            page.screenshot(path=str(target), full_page=True)
            written.append(target)
        browser.close()
    return written


def run_gate(
    start_cmd: str, health_url: str, base_url: str, routes: list[str], sha: str, out_dir: Path
) -> list[Path]:  # pragma: no cover (process+browser)
    """Boot the app (start_cmd), wait for health_url, screenshot routes, tear down.
    Always fail-soft."""
    port = str(free_port())
    proc = None
    try:
        proc = subprocess.Popen(start_cmd.format(port=port), shell=True)  # noqa: S602
        if not wait_for_url(health_url.format(port=port)):
            print("app_screenshot: app did not become healthy — skipping", file=sys.stderr)
            return []
        return screenshot_routes(base_url.format(port=port), routes, out_dir, sha)
    finally:
        if proc is not None:
            proc.terminate()


# --- CLI ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generic vis-UI screenshot gate (advisory)")
    p.add_argument("--start-cmd", required=True, help="launch command ({port} substituted)")
    p.add_argument("--health-url", required=True, help="readiness URL ({port} substituted)")
    p.add_argument("--base-url", required=True, help="base URL for routes ({port} substituted)")
    p.add_argument("--routes", nargs="+", default=["/"], help="routes to screenshot")
    p.add_argument("--sha", default="local")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = p.parse_args(argv)
    shots = run_gate(
        args.start_cmd, args.health_url, args.base_url, args.routes, args.sha, args.out_dir
    )
    if shots:
        print(f"app_screenshot: wrote {len(shots)} screenshot(s) to {args.out_dir}")
    return 0  # advisory: always exit 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

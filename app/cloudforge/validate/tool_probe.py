"""External-tool detection and invocation (fail-soft).

Optional tools (terraform / checkov / opa) may be absent. Detection is via
``shutil.which``; a missing tool yields a WARN outcome, never a failure. Network or
provider-download problems during ``terraform validate`` are classified WARN;
genuine syntax/config errors are FAIL.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_TIMEOUT_SECONDS = 120
_NETWORK_HINTS = ("registry", "network", "timeout", "connection", "dial tcp", "failed to download")


def detect_tool(name: str) -> bool:
    return shutil.which(name) is not None


@dataclass(frozen=True)
class ToolRun:
    """Result of invoking an external command."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def looks_like_network_issue(self) -> bool:
        blob = f"{self.stdout}\n{self.stderr}".lower()
        return any(hint in blob for hint in _NETWORK_HINTS)


def run_tool(command: list[str], cwd: Path | None = None) -> ToolRun:
    """Run a command capturing output; never raises on nonzero exit."""
    completed = subprocess.run(  # noqa: S603 - args are code-controlled tool invocations
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )
    return ToolRun(completed.returncode, completed.stdout, completed.stderr)

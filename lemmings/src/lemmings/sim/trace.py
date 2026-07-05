"""Append-only structured event recorder.

Used by invariant checks and Monte Carlo rollups. Optionally mirrors
events to a JSONL file for offline replay.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from lemmings.schemas import TraceEvent


class Trace:
    def __init__(self, jsonl_path: Path | None = None) -> None:
        self._events: list[TraceEvent] = []
        self._sink: IO[str] | None = None
        if jsonl_path is not None:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self._sink = jsonl_path.open("w", encoding="utf-8")

    def record(self, clock: float, kind: str, **payload: object) -> None:
        event = TraceEvent(clock=clock, kind=kind, payload=dict(payload))
        self._events.append(event)
        if self._sink is not None:
            self._sink.write(
                json.dumps(
                    {"clock": event.clock, "kind": event.kind, "payload": event.payload}
                )
                + "\n"
            )
            self._sink.flush()

    def events(self, kind: str | None = None) -> Iterator[TraceEvent]:
        for e in self._events:
            if kind is None or e.kind == kind:
                yield e

    def close(self) -> None:
        if self._sink is not None:
            self._sink.close()
            self._sink = None

    def __len__(self) -> int:
        return len(self._events)

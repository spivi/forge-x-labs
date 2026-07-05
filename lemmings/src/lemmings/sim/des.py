"""Heap-based discrete-event simulator.

Time is in minutes. Events are ordered by (clock, seq) so insertion
order breaks ties deterministically. The loop is single-threaded and
synchronous — callbacks may schedule new events.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Callback = Callable[["Clock"], None]


@dataclass(order=True)
class _Event:
    clock: float
    seq: int
    callback: Callback = field(compare=False)
    label: str = field(compare=False, default="")


class Clock:
    """The DES engine. Schedule callbacks; run pumps the heap."""

    def __init__(self) -> None:
        self._heap: list[_Event] = []
        self._now: float = 0.0
        self._seq: int = 0
        self._stopped: bool = False
        self.metadata: dict[str, Any] = {}

    @property
    def now(self) -> float:
        return self._now

    def schedule(self, delay: float, callback: Callback, label: str = "") -> None:
        """Schedule `callback` to fire `delay` minutes from now."""
        if delay < 0:
            raise ValueError(f"delay must be ≥ 0, got {delay}")
        self._seq += 1
        heapq.heappush(
            self._heap,
            _Event(clock=self._now + delay, seq=self._seq, callback=callback, label=label),
        )

    def schedule_at(self, when: float, callback: Callback, label: str = "") -> None:
        """Schedule `callback` to fire at absolute time `when`."""
        if when < self._now:
            raise ValueError(f"when={when} is in the past (now={self._now})")
        self.schedule(delay=when - self._now, callback=callback, label=label)

    def stop(self) -> None:
        self._stopped = True

    def run(self, until: float | None = None) -> None:
        """Pump events until the heap is empty, `until` is reached, or stop()."""
        while self._heap and not self._stopped:
            if until is not None and self._heap[0].clock > until:
                self._now = until
                return
            event = heapq.heappop(self._heap)
            self._now = event.clock
            event.callback(self)

    def pending(self) -> int:
        return len(self._heap)

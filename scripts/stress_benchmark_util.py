"""Shared timing/memory measurement helpers for the FXL-112 stress benchmark.

Pure measurement plumbing — no product behavior. ``measure`` wraps a zero-arg
callable with a wall-clock timer and ``tracemalloc`` peak-memory sample so every
benchmark stage reports the same three numbers (elapsed seconds, peak MiB, result)
without duplicating the try/finally dance at each call site.
"""

from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")

_BYTES_PER_MIB = 1024 * 1024


@dataclass(frozen=True)
class Measurement(Generic[T]):
    """One timed, memory-sampled call: its result plus the two headline numbers."""

    result: T
    elapsed_seconds: float
    peak_memory_mib: float


def measure(func: Callable[[], T]) -> Measurement[T]:
    """Run ``func`` once, tracking wall-clock time and peak ``tracemalloc`` memory.

    ``tracemalloc`` is started fresh (any prior trace is stopped first) so peak
    memory reflects only this stage, not accumulated state from an earlier one.
    """
    was_tracing = tracemalloc.is_tracing()
    tracemalloc.stop()
    tracemalloc.start()
    start = time.perf_counter()
    try:
        result = func()
    finally:
        elapsed = time.perf_counter() - start
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if was_tracing:
            tracemalloc.start()
    peak_mib = peak / _BYTES_PER_MIB
    return Measurement(result=result, elapsed_seconds=elapsed, peak_memory_mib=peak_mib)


@dataclass
class StageResult:
    """One reported benchmark stage at one scale (the JSON leaf unit)."""

    stage: str
    scale: int
    elapsed_seconds: float
    peak_memory_mib: float
    per_item_ms: float
    extra: dict[str, float | int | str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, float | int | str | dict[str, float | int | str]]:
        return {
            "stage": self.stage,
            "scale": self.scale,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "peak_memory_mib": round(self.peak_memory_mib, 3),
            "per_item_ms": round(self.per_item_ms, 5),
            **({"extra": self.extra} if self.extra else {}),
        }


def stage_result(
    stage: str,
    scale: int,
    measurement: Measurement[object],
    *,
    extra: dict[str, float | int | str] | None = None,
) -> StageResult:
    """Build a :class:`StageResult` from a completed :class:`Measurement`."""
    per_item_ms = (measurement.elapsed_seconds / scale) * 1000 if scale else 0.0
    return StageResult(
        stage=stage,
        scale=scale,
        elapsed_seconds=measurement.elapsed_seconds,
        peak_memory_mib=measurement.peak_memory_mib,
        per_item_ms=per_item_ms,
        extra=extra or {},
    )


def scaling_ratio(prev: StageResult, curr: StageResult) -> float | None:
    """``curr``/``prev`` elapsed-time ratio divided by the scale ratio.

    A value near 1.0 means linear scaling (10x the input -> ~10x the time). A value
    well above 1.0 (e.g. >2) at a 10x scale step flags likely super-linear behavior.
    Returns ``None`` when ``prev`` measured zero elapsed time (avoids a div-by-zero
    on a near-instant stage).
    """
    if prev.elapsed_seconds <= 0 or prev.scale <= 0:
        return None
    scale_ratio = curr.scale / prev.scale
    if scale_ratio <= 0:
        return None
    time_ratio = curr.elapsed_seconds / prev.elapsed_seconds
    return time_ratio / scale_ratio

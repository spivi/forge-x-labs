"""Tests for the discrete-event simulator."""

from __future__ import annotations

from lemmings.sim.des import Clock


def test_runs_in_clock_order() -> None:
    clock = Clock()
    fired: list[tuple[float, str]] = []
    clock.schedule(5.0, lambda c: fired.append((c.now, "b")))
    clock.schedule(1.0, lambda c: fired.append((c.now, "a")))
    clock.schedule(10.0, lambda c: fired.append((c.now, "c")))
    clock.run()
    assert [label for _, label in fired] == ["a", "b", "c"]
    assert [time for time, _ in fired] == [1.0, 5.0, 10.0]


def test_ties_break_by_insertion_order() -> None:
    clock = Clock()
    fired: list[str] = []
    clock.schedule(1.0, lambda c: fired.append("first"))
    clock.schedule(1.0, lambda c: fired.append("second"))
    clock.run()
    assert fired == ["first", "second"]


def test_schedule_at_absolute_time() -> None:
    clock = Clock()
    fired: list[float] = []
    clock.schedule(2.0, lambda c: clock.schedule_at(7.0, lambda c2: fired.append(c2.now)))
    clock.run()
    assert fired == [7.0]


def test_until_caps_clock() -> None:
    clock = Clock()
    fired: list[float] = []
    clock.schedule(5.0, lambda c: fired.append(c.now))
    clock.schedule(15.0, lambda c: fired.append(c.now))
    clock.run(until=10.0)
    assert fired == [5.0]
    assert clock.pending() == 1
    assert clock.now == 10.0


def test_stop_halts_loop() -> None:
    clock = Clock()
    fired: list[str] = []

    def stopper(c: Clock) -> None:
        fired.append("stop")
        c.stop()

    clock.schedule(1.0, stopper)
    clock.schedule(2.0, lambda c: fired.append("after"))
    clock.run()
    assert fired == ["stop"]


def test_negative_delay_rejected() -> None:
    clock = Clock()
    try:
        clock.schedule(-1.0, lambda c: None)
    except ValueError:
        return
    raise AssertionError("expected ValueError for negative delay")

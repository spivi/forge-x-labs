"""Agent Protocol — every agent (sim or real) implements `run`.

`run` is invoked by the orchestrator at the appropriate clock time. It
mutates `world` (records ledger rows, opens PRs, records reviews) and
schedules follow-on events on `clock`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from lemmings.schemas import AgentKind
from lemmings.sim.des import Clock
from lemmings.sim.trace import Trace
from lemmings.world.protocol import World


@runtime_checkable
class Agent(Protocol):
    kind: AgentKind

    def run(self, clock: Clock, world: World, trace: Trace, ticket_id: str) -> None:
        """Execute one stage of work for `ticket_id`."""
        ...

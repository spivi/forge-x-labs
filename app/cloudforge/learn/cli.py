"""The ``cloudforge learn`` Typer command group (STUB — implemented in ticket #15).

Wires the pipeline to the user as a nested ``learn`` sub-command group on
``app.cloudforge.cli.app``: ``fetch-sources``, ``ingest --adapter <name>``,
``validate-corpus``, ``summarize``, ``export-training [--include-restricted]``. All
commands stay thin — they call ``learn/`` modules and print with ``rich``. No CLI wiring
lives here in the foundation ticket.

See design §10.
"""

from __future__ import annotations

# Implemented in ticket #15 (Add learn CLI commands).

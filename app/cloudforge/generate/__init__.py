"""Scenario generators: a deterministic template generator and the seeded graph
composer, both behind the same ``ScenarioGenerator`` interface.

Future engines (LLM, Modal batch, diffusion) plug in behind that same interface
without touching the pipeline.
"""

from __future__ import annotations

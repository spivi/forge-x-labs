"""Scenario generators. MVP ships one deterministic template generator.

Future engines (LLM, Modal batch, diffusion) plug in behind the same
``ScenarioGenerator`` interface without touching the pipeline.
"""

from __future__ import annotations

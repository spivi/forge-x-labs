"""Shared pytest fixtures and hypothesis profiles."""

from __future__ import annotations

from hypothesis import settings

settings.register_profile("ci", derandomize=True, deadline=None)
settings.register_profile("dev", deadline=None)

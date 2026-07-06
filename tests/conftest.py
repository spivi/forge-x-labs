"""Test configuration and shared fixtures.

Add project-specific fixtures here following the patterns
described in .dev-context/rules/testing.md.

Patterns to follow:
- Use `app.dependency_overrides` to swap dependencies in API tests
- Mock at the boundary: replace repositories in service tests
- External services: always mocked, never called in tests
- Use `unittest.mock.AsyncMock` for async callables
"""

from __future__ import annotations

from hypothesis import settings

# Register deterministic hypothesis profiles for CI and development.
# CI profile: derandomize=True ensures byte-identical output across runs (S10),
# and prevents flakiness from the test execution environment (no wall-clock/PID/RNG state).
# Dev profile: allows randomization for better coverage discovery during local development.
settings.register_profile("ci", derandomize=True, deadline=None)
settings.register_profile("dev", deadline=None)

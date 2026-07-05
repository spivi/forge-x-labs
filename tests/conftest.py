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

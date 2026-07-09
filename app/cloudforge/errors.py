"""Custom exceptions for cloudforge.

Business errors are explicit types so callers never catch bare ``Exception``.
"""

from __future__ import annotations


class CloudforgeError(Exception):
    """Base class for all cloudforge errors."""


class ScenarioLoadError(CloudforgeError):
    """A scenario input file is missing, unreadable, or fails schema validation."""


class GraphIntegrityError(CloudforgeError):
    """A generated graph is internally inconsistent (dangling edges, etc.)."""


class UnknownScenarioTypeError(CloudforgeError):
    """A scenario requests a ``scenario_type`` with no registered generator."""


class UnknownEngineError(CloudforgeError):
    """The CLI ``--engine`` option names an engine that does not exist."""


class ValidationFailedError(CloudforgeError):
    """One or more validation checks failed (used to signal a nonzero exit)."""

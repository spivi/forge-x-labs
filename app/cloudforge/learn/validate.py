"""Graph-fragment validation rules (STUB — implemented in ticket #9).

A fragment is valid only if (design §9.2): edge endpoints resolve, node/edge types are
known-or-generic, expected findings reference existing fragment resources, and no
forbidden destructive action appears (reusing ``constants.FORBIDDEN_PERMISSION_PATTERNS``
— a match marks the pattern ``unsafe_operational`` and rejects it). ``validation_status``
becomes ``valid`` only when all four pass. No validation logic lives here in the
foundation ticket.
"""

from __future__ import annotations

# Implemented in ticket #9 (Implement graph fragment validation).

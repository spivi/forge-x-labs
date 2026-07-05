"""Training-export gate + writer (STUB — implemented in ticket #13).

A pattern is exported only if ALL hold (design §9.6): ``validation_status == valid``,
``training_eligible == true``, ``safety_classification`` in the trainable set,
``reuse_status`` allows reuse, ``allowed_for_training == true``, and
``quality_score >= 0.70``. ``restricted_source`` / ``unsafe_operational`` / ``unknown``
are excluded; a ``--include-restricted`` flag can override ``restricted_source`` (never
``unsafe_operational``) and records that it was used. The export is a versioned JSON/JSONL
bundle with a coverage manifest. No export logic lives here in the foundation ticket.
"""

from __future__ import annotations

# Implemented in ticket #13 (Implement training export).

"""Unsafe-operational content scan for the normalizer (design §9.1).

A small, deterministic, keyword + secret-pattern scan — NOT ML, NOT a classifier.
Any match forces ``safety_classification = unsafe_operational`` regardless of how
permissive the source's ``reuse_status`` otherwise is (design §1 hard non-goal: never
ingest offensive/operational-attack content). Split out of ``normalizer.py`` to keep
that module under the 200-line cap (rules/general.md).
"""

from __future__ import annotations

import re

_UNSAFE_KEYWORDS: tuple[str, ...] = (
    "exploit",
    "persistence",
    "evasion",
    "credential-theft",
    "credential theft",
    "malware",
    "payload",
    "destructive-action",
    "destructive action",
    "backdoor",
)

_PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_SECRET_LIKE_PATTERN = re.compile(
    r"\b(?:aws_secret_access_key|api[_-]?key|password)\s*[:=]\s*['\"]?[A-Za-z0-9/+=_-]{12,}"
)


def is_unsafe_content(*fields: str) -> bool:
    """Return ``True`` if any field looks like unsafe-operational content.

    Conservative keyword scan (exploit/persistence/evasion/credential-theft/
    malware/payload/destructive-action/backdoor wording) plus a real-looking
    private-key or secret-assignment pattern.
    """
    haystack = " ".join(fields)
    lowered = haystack.lower()
    if any(keyword in lowered for keyword in _UNSAFE_KEYWORDS):
        return True
    if _PRIVATE_KEY_PATTERN.search(haystack):
        return True
    return bool(_SECRET_LIKE_PATTERN.search(haystack))

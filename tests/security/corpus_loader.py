"""Loader for the file-based hostile corpus (``tests/security/corpus/*.txt``).

The hostile-value corpus lives in plain ``.txt``
files (not hardcoded in a Python module) so it is easy to audit, diff, and extend
without touching test code. Each non-comment, non-blank line is a single Python
string-literal, parsed with ``ast.literal_eval`` — plain newline-delimited text
cannot represent several REQUIRED payloads verbatim (an embedded literal newline, a
tab, or a NUL byte), so a quoted-literal-per-line format is used instead of raw text.
"""

from __future__ import annotations

import ast
from pathlib import Path

_CORPUS_DIR = Path(__file__).parent / "corpus"


def load_corpus_file(name: str) -> list[str]:
    """Parse ``tests/security/corpus/<name>`` into a list of hostile string values.

    Blank lines and lines starting with ``#`` are skipped. Every remaining line MUST
    be a valid Python string-literal (``ast.literal_eval``d) — a malformed line is a
    corpus authoring bug, so it fails loudly rather than being silently skipped.
    """
    path = _CORPUS_DIR / name
    values: list[str] = []
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parsed = ast.literal_eval(line)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(
                f"{path}:{lineno}: not a valid Python string literal: {line!r}"
            ) from exc
        if not isinstance(parsed, str):
            raise TypeError(
                f"{path}:{lineno}: expected a str literal, got {type(parsed).__name__}"
            )
        values.append(parsed)
    return values


def load_hcl_strings() -> list[str]:
    return load_corpus_file("hcl_strings.txt")


def load_resource_ids() -> list[str]:
    return load_corpus_file("resource_ids.txt")


def load_tag_values() -> list[str]:
    return load_corpus_file("tag_values.txt")

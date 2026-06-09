"""Shared extraction-chain utilities.

Centralises two patterns that were duplicated across every parser module:

1. ``has_content``  — the ``text is not None and bool(text.strip())`` check
   that appeared 8+ times.
2. ``run_extraction_chain`` — the "try A → try B → … → raise" fallback loop
   with status printing that was copy-pasted for EPUB, PDF, DOCX, and RTF.
"""

from __future__ import annotations

from extractor.exceptions import ExtractionError


def has_content(text: str | None) -> bool:
    """Return True when *text* contains at least one non-whitespace char."""
    return text is not None and bool(text.strip())


def run_extraction_chain(
    extractors: list[tuple[str, object]],
    *,
    error_message: str,
) -> tuple[str, str]:
    """Try *extractors* in order; return ``(text, method_name)`` on first hit.

    Parameters
    ----------
    extractors:
        ``[(name, zero_arg_callable), ...]``.  *name* is used both in the
        ``Trying <name>...`` status line and as the returned method identifier.
    error_message:
        Passed to :class:`ExtractionError` when every extractor fails.

    Raises
    ------
    ExtractionError
        If no extractor produces usable text.
    """
    last_idx = len(extractors) - 1
    for i, (name, fn) in enumerate(extractors):
        print(f"Trying {name}...", end=" ", flush=True)
        text = fn()
        if has_content(text):
            print("OK")
            return text, name
        print("FAILED" if i == last_idx else "not available")

    raise ExtractionError(error_message)

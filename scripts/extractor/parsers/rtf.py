import html
import re
from extractor.chain import run_extraction_chain
from extractor.exceptions import ExtractionError
from extractor.parsers.text import read_text_file


def strip_rtf_fallback(raw: str) -> str:
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    raw = re.sub(r"\\par[d]?", "\n", raw)
    raw = re.sub(r"\\tab", "\t", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", raw)
    raw = raw.replace("{", "").replace("}", "")
    return html.unescape(raw)


def _try_striprtf(raw: str) -> str | None:
    try:
        from striprtf.striprtf import rtf_to_text
        text = rtf_to_text(raw)
        return text if text.strip() else None
    except ImportError:
        return None
    except Exception:
        return None


def extract_rtf(rtf_path: str) -> tuple[str, str]:
    """High-level RTF extraction with automatic fallback.

    Tries striprtf first, then a regex-based cleanup.
    Returns ``(text, method_name)``.
    """
    raw = read_text_file(rtf_path)
    if raw is None:
        raise ExtractionError(f"Could not read RTF file: {rtf_path}")

    return run_extraction_chain(
        [
            ("striprtf", lambda: _try_striprtf(raw)),
            ("rtf-regex", lambda: strip_rtf_fallback(raw)),
        ],
        error_message=f"Could not extract text from RTF: {rtf_path}",
    )

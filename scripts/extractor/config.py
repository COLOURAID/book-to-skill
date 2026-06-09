import os
import stat
import tempfile
from pathlib import Path


def _resolve_workdir() -> Path:
    """Return the working directory for extraction output.

    Uses ``BOOK_SKILL_WORKDIR`` if set; otherwise creates a per-user
    directory under the system temp dir with restrictive permissions
    (owner-only) to prevent information leaks on shared systems.
    """
    env_dir = os.environ.get("BOOK_SKILL_WORKDIR")
    if env_dir:
        return Path(env_dir)

    base = Path(tempfile.gettempdir()) / f"book_skill_work_{os.getuid()}"
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Tighten permissions in case the directory already existed with
    # broader permissions from a previous run.
    try:
        base.chmod(stat.S_IRWXU)
    except OSError:
        pass
    return base


OUTPUT_DIR = _resolve_workdir()
OUTPUT_TEXT = OUTPUT_DIR / "full_text.txt"
OUTPUT_META = OUTPUT_DIR / "metadata.json"

WORDS_PER_TOKEN = 0.75  # approximate

TEXT_EXTENSIONS = {".txt", ".text", ".md", ".markdown", ".rst", ".adoc", ".asciidoc"}
HTML_EXTENSIONS = {".html", ".htm", ".xhtml"}
CALIBRE_EBOOK_EXTENSIONS = {".mobi", ".azw", ".azw3"}
SUPPORTED_EXTENSIONS = {
    ".pdf", ".epub", ".docx", ".rtf",
    *TEXT_EXTENSIONS,
    *HTML_EXTENSIONS,
    *CALIBRE_EBOOK_EXTENSIONS,
}

PYTHON_DEPENDENCIES = {
    "docling": "docling",
    "PyPDF2": "PyPDF2",
    "pdfminer": "pdfminer.six",
    "ebooklib": "ebooklib",
    "bs4": "beautifulsoup4",
    "docx": "python-docx",
    "striprtf": "striprtf",
}


def supported_formats_message() -> str:
    return ", ".join(sorted(SUPPORTED_EXTENSIONS))

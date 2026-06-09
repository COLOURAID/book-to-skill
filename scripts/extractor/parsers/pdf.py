import shutil
import subprocess
from extractor.chain import has_content, run_extraction_chain


def extract_with_pdftotext(pdf_path: str) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except Exception:
        pass
    return None


def extract_with_pypdf2(pdf_path: str) -> str | None:
    try:
        import PyPDF2
        text_parts = []
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    text_parts.append(page.extract_text() or "")
                except Exception:
                    text_parts.append("")
        return "\n".join(text_parts)
    except ImportError:
        return None
    except Exception:
        return None


def extract_with_pdfminer(pdf_path: str) -> str | None:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(pdf_path)
    except ImportError:
        return None
    except Exception:
        return None


def extract_with_docling(pdf_path: str) -> str | None:
    """Layout-aware extraction using Docling. Best for technical books with tables and code."""
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        result = converter.convert(pdf_path)
        return result.document.export_to_markdown()
    except ImportError:
        return None
    except Exception:
        return None


def count_pages(pdf_path: str) -> int:
    # Try pdfinfo first
    if shutil.which("pdfinfo"):
        try:
            result = subprocess.run(
                ["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15
            )
            for line in result.stdout.splitlines():
                if line.startswith("Pages:"):
                    return int(line.split(":")[1].strip())
        except Exception:
            pass
    # Fallback: count pages via PyPDF2
    try:
        import PyPDF2
        with open(pdf_path, "rb") as f:
            return len(PyPDF2.PdfReader(f).pages)
    except Exception:
        return 0


def extract_pdf(pdf_path: str, extraction_mode: str) -> tuple[str, str]:
    """High-level PDF extraction with mode-aware fallback.

    *technical* mode tries Docling first (layout-aware), then falls through
    to the text chain.  *text* mode goes straight to pdftotext → PyPDF2 →
    pdfminer.

    Returns ``(text, method_name)``.
    """
    if extraction_mode == "technical":
        print("Mode: technical \u2014 using Docling (layout-aware)...", end=" ", flush=True)
        text = extract_with_docling(pdf_path)
        if has_content(text):
            print("OK")
            return text, "docling"
        print("not available, falling back to text chain")

    print("Mode: text \u2014 using pdftotext...")
    return run_extraction_chain(
        [
            ("pdftotext", lambda: extract_with_pdftotext(pdf_path)),
            ("PyPDF2", lambda: extract_with_pypdf2(pdf_path)),
            ("pdfminer", lambda: extract_with_pdfminer(pdf_path)),
        ],
        error_message=(
            "Could not extract text from PDF.\n"
            "Install one of: poppler-utils (pdftotext), PyPDF2, or pdfminer.six\n"
            "  sudo apt install poppler-utils\n"
            "  pip3 install PyPDF2\n"
            "  pip3 install pdfminer.six"
        ),
    )

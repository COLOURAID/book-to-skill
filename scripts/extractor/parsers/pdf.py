import shutil
import subprocess
import sys


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
        if result.returncode != 0:
            print(f"pdftotext exited with code {result.returncode}: {result.stderr.strip()}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"pdftotext timed out on {pdf_path}", file=sys.stderr)
    except ImportError:
        pass
    except Exception as exc:
        print(f"pdftotext failed on {pdf_path}: {exc}", file=sys.stderr)
    return None


def extract_with_pypdf2(pdf_path: str) -> str | None:
    try:
        import PyPDF2
        text_parts = []
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                try:
                    text_parts.append(page.extract_text() or "")
                except Exception as exc:
                    print(f"PyPDF2: failed to extract page {i + 1} of {pdf_path}: {exc}", file=sys.stderr)
                    text_parts.append("")
        return "\n".join(text_parts)
    except ImportError:
        return None
    except Exception as exc:
        print(f"PyPDF2 failed on {pdf_path}: {exc}", file=sys.stderr)
        return None


def extract_with_pdfminer(pdf_path: str) -> str | None:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(pdf_path)
    except ImportError:
        return None
    except Exception as exc:
        print(f"pdfminer failed on {pdf_path}: {exc}", file=sys.stderr)
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
    except Exception as exc:
        print(f"docling failed on {pdf_path}: {exc}", file=sys.stderr)
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
        except Exception as exc:
            print(f"pdfinfo failed on {pdf_path}: {exc}", file=sys.stderr)
    # Fallback: count pages with PyPDF2
    try:
        import PyPDF2
        with open(pdf_path, "rb") as f:
            return len(PyPDF2.PdfReader(f).pages)
    except ImportError:
        return 0
    except Exception as exc:
        print(f"count_pages: PyPDF2 failed on {pdf_path}: {exc}", file=sys.stderr)
        return 0

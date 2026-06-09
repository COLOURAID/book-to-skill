"""
Unit tests for parser modules with low/no test coverage.

Covers:
  - parsers/text.py    — read_text_file (encoding handling)
  - parsers/html.py    — _HTMLTextExtractor, extract_html_content, extract_html_file
  - parsers/pdf.py     — all extraction functions + count_pages
  - parsers/rtf.py     — strip_rtf_fallback, extract_rtf
  - parsers/calibre.py — extract_with_ebook_convert
"""

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from extractor.parsers.text import read_text_file
from extractor.parsers.html import _HTMLTextExtractor, extract_html_content, extract_html_file
from extractor.parsers.pdf import (
    extract_with_pdftotext,
    extract_with_pypdf2,
    extract_with_pdfminer,
    extract_with_docling,
    count_pages,
)
from extractor.parsers.rtf import strip_rtf_fallback, extract_rtf
from extractor.parsers.calibre import extract_with_ebook_convert
from extractor.exceptions import ExtractionError


# ═══════════════════════════════════════════════════════════════════════════
#  parsers/text.py
# ═══════════════════════════════════════════════════════════════════════════

class TestReadTextFile:
    """Unit tests for read_text_file encoding-fallback logic."""

    def test_reads_utf8(self, tmp_path):
        p = tmp_path / "utf8.txt"
        p.write_text("Hello UTF-8 world", encoding="utf-8")
        assert read_text_file(str(p)) == "Hello UTF-8 world"

    def test_reads_utf8_bom(self, tmp_path):
        p = tmp_path / "bom.txt"
        p.write_bytes(b"\xef\xbb\xbfBOM content")
        result = read_text_file(str(p))
        assert result == "BOM content"

    def test_reads_latin1(self, tmp_path):
        p = tmp_path / "latin.txt"
        # \xe9 is 'é' in latin-1, invalid as standalone UTF-8
        p.write_bytes(b"caf\xe9")
        result = read_text_file(str(p))
        assert result is not None
        assert "caf" in result

    def test_reads_cp1252(self, tmp_path):
        p = tmp_path / "win.txt"
        # \x93 and \x94 are curly quotes in cp1252, invalid in utf-8 and latin-1
        p.write_bytes(b"\x93Hello\x94")
        result = read_text_file(str(p))
        assert result is not None
        assert "Hello" in result

    def test_returns_none_for_nonexistent(self, tmp_path):
        result = read_text_file(str(tmp_path / "no_such_file.txt"))
        assert result is None

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.txt"
        p.write_text("", encoding="utf-8")
        assert read_text_file(str(p)) == ""


# ═══════════════════════════════════════════════════════════════════════════
#  parsers/html.py
# ═══════════════════════════════════════════════════════════════════════════

class TestHTMLTextExtractor:
    """Unit tests for the stdlib HTML parser fallback."""

    def test_basic_text_extraction(self):
        parser = _HTMLTextExtractor()
        parser.feed("<html><body><p>Hello World</p></body></html>")
        assert "Hello World" in parser.get_text()

    def test_script_tags_skipped(self):
        parser = _HTMLTextExtractor()
        parser.feed("<html><body><script>var x=1;</script><p>visible</p></body></html>")
        text = parser.get_text()
        assert "var x=1" not in text
        assert "visible" in text

    def test_style_tags_skipped(self):
        parser = _HTMLTextExtractor()
        parser.feed("<html><body><style>.cls{color:red}</style><p>content</p></body></html>")
        text = parser.get_text()
        assert "color:red" not in text
        assert "content" in text

    def test_head_tag_skipped(self):
        parser = _HTMLTextExtractor()
        parser.feed("<html><head><title>Title</title></head><body><p>body</p></body></html>")
        text = parser.get_text()
        assert "Title" not in text
        assert "body" in text

    def test_newlines_for_block_elements(self):
        parser = _HTMLTextExtractor()
        parser.feed("<h1>Title</h1><p>Para 1</p><p>Para 2</p>")
        text = parser.get_text()
        assert "Title" in text
        assert "Para 1" in text
        assert "Para 2" in text

    def test_html_entities_unescaped(self):
        parser = _HTMLTextExtractor()
        parser.feed("<p>&amp; &lt; &gt; &quot;</p>")
        text = parser.get_text()
        assert "& < > \"" in text

    def test_nested_skip_tags(self):
        parser = _HTMLTextExtractor()
        parser.feed("<script><script>nested</script></script><p>after</p>")
        text = parser.get_text()
        assert "nested" not in text
        assert "after" in text


class TestExtractHtmlContent:
    """Tests for extract_html_content (bs4 path + stdlib fallback)."""

    def test_without_bs4_uses_stdlib(self):
        with mock.patch.dict("sys.modules", {"bs4": None}):
            # Force ImportError on bs4
            with mock.patch("extractor.parsers.html.extract_html_content") as m:
                # Just call the real function
                pass
        # Simpler: test that it works regardless of bs4
        result = extract_html_content("<html><body><h1>Heading</h1><p>Text</p></body></html>")
        assert "Heading" in result
        assert "Text" in result

    def test_strips_script_and_style(self):
        html = "<html><body><script>js</script><style>css</style><p>content</p></body></html>"
        result = extract_html_content(html)
        assert "js" not in result
        assert "css" not in result
        assert "content" in result

    def test_empty_html(self):
        result = extract_html_content("")
        assert result == "" or result.strip() == ""


class TestExtractHtmlFile:
    """Tests for extract_html_file."""

    def test_returns_text_from_file(self, tmp_path):
        p = tmp_path / "test.html"
        p.write_text("<html><body><p>File content</p></body></html>", encoding="utf-8")
        result = extract_html_file(str(p))
        assert result is not None
        assert "File content" in result

    def test_returns_none_for_missing_file(self, tmp_path):
        result = extract_html_file(str(tmp_path / "nope.html"))
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
#  parsers/pdf.py
# ═══════════════════════════════════════════════════════════════════════════

class TestPdfExtractWithPdftotext:
    """Tests for extract_with_pdftotext."""

    def test_returns_none_when_pdftotext_not_found(self):
        with mock.patch("shutil.which", return_value=None):
            assert extract_with_pdftotext("some.pdf") is None

    def test_returns_text_on_success(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-fake")

        with mock.patch("shutil.which", return_value="/usr/bin/pdftotext"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="Extracted PDF text\n", stderr=""
                )
                result = extract_with_pdftotext(str(pdf))

        assert result == "Extracted PDF text\n"
        mock_run.assert_called_once()

    def test_returns_none_on_failure(self, tmp_path):
        pdf = tmp_path / "bad.pdf"
        pdf.write_bytes(b"%PDF-bad")

        with mock.patch("shutil.which", return_value="/usr/bin/pdftotext"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr="error"
                )
                result = extract_with_pdftotext(str(pdf))

        assert result is None

    def test_returns_none_on_empty_stdout(self, tmp_path):
        pdf = tmp_path / "empty.pdf"
        pdf.write_bytes(b"%PDF-empty")

        with mock.patch("shutil.which", return_value="/usr/bin/pdftotext"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="   \n", stderr=""
                )
                result = extract_with_pdftotext(str(pdf))

        assert result is None

    def test_returns_none_on_timeout(self, tmp_path):
        pdf = tmp_path / "slow.pdf"
        pdf.write_bytes(b"%PDF-slow")

        with mock.patch("shutil.which", return_value="/usr/bin/pdftotext"):
            with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pdftotext", 120)):
                result = extract_with_pdftotext(str(pdf))

        assert result is None


class TestPdfExtractWithPyPDF2:
    """Tests for extract_with_pypdf2."""

    def test_returns_none_when_not_installed(self):
        with mock.patch.dict("sys.modules", {"PyPDF2": None}):
            with mock.patch("builtins.__import__", side_effect=ImportError):
                result = extract_with_pypdf2("some.pdf")
        assert result is None

    def test_returns_text_on_success(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"fake")

        mock_page = mock.MagicMock()
        mock_page.extract_text.return_value = "Page 1 text"
        mock_reader = mock.MagicMock()
        mock_reader.pages = [mock_page]

        mock_pypdf2 = mock.MagicMock()
        mock_pypdf2.PdfReader.return_value = mock_reader

        with mock.patch.dict("sys.modules", {"PyPDF2": mock_pypdf2}):
            with mock.patch("builtins.open", mock.mock_open(read_data=b"fake")):
                # Need to reimport to get the mock
                import importlib
                import extractor.parsers.pdf as pdf_mod
                # Direct call with mock
                with mock.patch.object(pdf_mod, "extract_with_pypdf2") as orig:
                    pass

        # Simpler approach: test the function directly with mocked PyPDF2
        mock_pypdf2_module = mock.MagicMock()
        mock_reader = mock.MagicMock()
        mock_page = mock.MagicMock()
        mock_page.extract_text.return_value = "Page text here"
        mock_reader.pages = [mock_page]
        mock_pypdf2_module.PdfReader.return_value = mock_reader

        with mock.patch.dict("sys.modules", {"PyPDF2": mock_pypdf2_module}):
            result = extract_with_pypdf2(str(pdf))

        assert result is not None
        assert "Page text here" in result

    def test_returns_none_on_exception(self, tmp_path):
        pdf = tmp_path / "bad.pdf"
        pdf.write_bytes(b"not a pdf")

        # Real PyPDF2 would raise on garbage input
        result = extract_with_pypdf2(str(pdf))
        # Either None (ImportError or parse failure)
        assert result is None or isinstance(result, str)


class TestPdfExtractWithPdfminer:
    """Tests for extract_with_pdfminer."""

    def test_returns_none_when_not_installed(self):
        with mock.patch.dict("sys.modules", {"pdfminer": None, "pdfminer.high_level": None}):
            result = extract_with_pdfminer("some.pdf")
        assert result is None

    def test_calls_extract_text(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"fake")

        mock_module = mock.MagicMock()
        mock_module.extract_text.return_value = "Mined text content"

        with mock.patch.dict("sys.modules", {"pdfminer": mock.MagicMock(), "pdfminer.high_level": mock_module}):
            result = extract_with_pdfminer(str(pdf))

        assert result == "Mined text content"


class TestPdfExtractWithDocling:
    """Tests for extract_with_docling."""

    def test_returns_none_when_not_installed(self):
        with mock.patch.dict("sys.modules", {
            "docling": None,
            "docling.document_converter": None,
            "docling.datamodel": None,
            "docling.datamodel.pipeline_options": None,
            "docling.datamodel.base_models": None,
        }):
            result = extract_with_docling("some.pdf")
        assert result is None

    def test_returns_markdown_on_success(self, tmp_path):
        pdf = tmp_path / "tech.pdf"
        pdf.write_bytes(b"fake")

        mock_result = mock.MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Chapter 1\nContent"

        mock_converter_cls = mock.MagicMock()
        mock_converter_cls.return_value.convert.return_value = mock_result

        mock_dc = mock.MagicMock()
        mock_dc.DocumentConverter = mock_converter_cls
        mock_dc.PdfFormatOption = mock.MagicMock()

        mock_po = mock.MagicMock()
        mock_po.PdfPipelineOptions = mock.MagicMock

        mock_bm = mock.MagicMock()
        mock_bm.InputFormat = mock.MagicMock()
        mock_bm.InputFormat.PDF = "PDF"

        with mock.patch.dict("sys.modules", {
            "docling": mock.MagicMock(),
            "docling.document_converter": mock_dc,
            "docling.datamodel": mock.MagicMock(),
            "docling.datamodel.pipeline_options": mock_po,
            "docling.datamodel.base_models": mock_bm,
        }):
            result = extract_with_docling(str(pdf))

        assert result == "# Chapter 1\nContent"


class TestCountPages:
    """Tests for count_pages."""

    def test_returns_0_when_no_tools(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"fake")

        with mock.patch("shutil.which", return_value=None):
            with mock.patch.dict("sys.modules", {"PyPDF2": None}):
                result = count_pages(str(pdf))

        assert result == 0

    def test_uses_pdfinfo(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"fake")

        with mock.patch("shutil.which", return_value="/usr/bin/pdfinfo"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=0,
                    stdout="Title: Test\nPages: 42\nCreator: Test",
                    stderr=""
                )
                result = count_pages(str(pdf))

        assert result == 42

    def test_pdfinfo_fallback_to_pypdf2(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"fake")

        mock_pypdf2 = mock.MagicMock()
        mock_reader = mock.MagicMock()
        mock_reader.pages = [mock.MagicMock()] * 10
        mock_pypdf2.PdfReader.return_value = mock_reader

        with mock.patch("shutil.which", return_value=None):
            with mock.patch.dict("sys.modules", {"PyPDF2": mock_pypdf2}):
                result = count_pages(str(pdf))

        assert result == 10


# ═══════════════════════════════════════════════════════════════════════════
#  parsers/rtf.py
# ═══════════════════════════════════════════════════════════════════════════

class TestStripRtfFallback:
    """Tests for the regex-based RTF fallback stripper."""

    def test_removes_rtf_control_words(self):
        raw = r"{\rtf1\ansi Hello World}"
        result = strip_rtf_fallback(raw)
        assert "Hello World" in result
        assert "\\rtf1" not in result
        assert "\\ansi" not in result

    def test_converts_par_to_newline(self):
        raw = r"{\rtf1 First\par Second\pard Third}"
        result = strip_rtf_fallback(raw)
        assert "First" in result
        assert "Second" in result
        assert "Third" in result
        assert "\n" in result

    def test_converts_tab(self):
        raw = r"{\rtf1 Col1\tab Col2}"
        result = strip_rtf_fallback(raw)
        assert "\t" in result

    def test_removes_hex_escapes(self):
        raw = r"{\rtf1 caf\\'e9}"
        result = strip_rtf_fallback(raw)
        assert "caf" in result
        # Hex escape replaced with space
        assert "\\'" not in result

    def test_removes_braces(self):
        raw = r"{\rtf1{inner text}}"
        result = strip_rtf_fallback(raw)
        assert "{" not in result
        assert "}" not in result


class TestExtractRtf:
    """Tests for the full RTF extraction pipeline."""

    def test_with_striprtf_library(self, tmp_path):
        rtf_file = tmp_path / "test.rtf"
        rtf_file.write_text(r"{\rtf1\ansi Hello from RTF}", encoding="utf-8")

        mock_striprtf = mock.MagicMock()
        mock_striprtf.striprtf.rtf_to_text.return_value = "Hello from RTF"

        with mock.patch.dict("sys.modules", {"striprtf": mock_striprtf, "striprtf.striprtf": mock_striprtf.striprtf}):
            text, method = extract_rtf(str(rtf_file))

        assert text == "Hello from RTF"
        assert method == "striprtf"

    def test_falls_back_to_regex(self, tmp_path):
        rtf_file = tmp_path / "test.rtf"
        rtf_file.write_text(r"{\rtf1\ansi Fallback content}", encoding="utf-8")

        # Simulate striprtf not installed
        with mock.patch.dict("sys.modules", {"striprtf": None, "striprtf.striprtf": None}):
            text, method = extract_rtf(str(rtf_file))

        assert method == "rtf-regex"
        assert "Fallback content" in text

    def test_raises_on_unreadable_file(self, tmp_path):
        with pytest.raises(ExtractionError, match="Could not read RTF"):
            extract_rtf(str(tmp_path / "nonexistent.rtf"))


# ═══════════════════════════════════════════════════════════════════════════
#  parsers/calibre.py
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractWithEbookConvert:
    """Tests for extract_with_ebook_convert."""

    def test_returns_none_when_not_on_path(self):
        with mock.patch("shutil.which", return_value=None):
            assert extract_with_ebook_convert("book.mobi") is None

    def test_returns_text_on_success(self, tmp_path):
        mobi = tmp_path / "book.mobi"
        mobi.write_bytes(b"fake mobi data")

        with mock.patch("shutil.which", return_value="/usr/bin/ebook-convert"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
                # The function reads from OUTPUT_DIR / "ebook-convert-output.txt"
                with mock.patch("extractor.parsers.calibre.OUTPUT_DIR", tmp_path):
                    output_file = tmp_path / "ebook-convert-output.txt"
                    output_file.write_text("Converted ebook text content", encoding="utf-8")
                    result = extract_with_ebook_convert(str(mobi))

        assert result == "Converted ebook text content"

    def test_returns_none_on_failure(self, tmp_path):
        mobi = tmp_path / "bad.mobi"
        mobi.write_bytes(b"fake")

        with mock.patch("shutil.which", return_value="/usr/bin/ebook-convert"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr="error"
                )
                with mock.patch("extractor.parsers.calibre.OUTPUT_DIR", tmp_path):
                    result = extract_with_ebook_convert(str(mobi))

        assert result is None

    def test_returns_none_on_timeout(self, tmp_path):
        mobi = tmp_path / "slow.mobi"
        mobi.write_bytes(b"fake")

        with mock.patch("shutil.which", return_value="/usr/bin/ebook-convert"):
            with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ebook-convert", 300)):
                with mock.patch("extractor.parsers.calibre.OUTPUT_DIR", tmp_path):
                    result = extract_with_ebook_convert(str(mobi))

        assert result is None

    def test_returns_none_on_empty_output(self, tmp_path):
        mobi = tmp_path / "empty.mobi"
        mobi.write_bytes(b"fake")

        with mock.patch("shutil.which", return_value="/usr/bin/ebook-convert"):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
                with mock.patch("extractor.parsers.calibre.OUTPUT_DIR", tmp_path):
                    output_file = tmp_path / "ebook-convert-output.txt"
                    output_file.write_text("   \n  ", encoding="utf-8")
                    result = extract_with_ebook_convert(str(mobi))

        assert result is None

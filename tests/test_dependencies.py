"""
Unit tests for extractor/dependencies.py.

Covers:
  - python_module_available
  - missing_python_packages
  - install_python_packages
  - normalize_install_mode
  - offer_dependency_install
  - prepare_dependencies
"""

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from extractor.dependencies import (
    python_module_available,
    missing_python_packages,
    install_python_packages,
    normalize_install_mode,
    offer_dependency_install,
    prepare_dependencies,
)


# ═══════════════════════════════════════════════════════════════════════════
#  python_module_available
# ═══════════════════════════════════════════════════════════════════════════

class TestPythonModuleAvailable:
    """Tests for python_module_available."""

    def test_builtin_module_available(self):
        assert python_module_available("os") is True

    def test_nonexistent_module_not_available(self):
        assert python_module_available("nonexistent_xyz_module_999") is False

    def test_pytest_available(self):
        assert python_module_available("pytest") is True


# ═══════════════════════════════════════════════════════════════════════════
#  missing_python_packages
# ═══════════════════════════════════════════════════════════════════════════

class TestMissingPythonPackages:
    """Tests for missing_python_packages."""

    def test_no_missing_when_all_installed(self):
        with mock.patch("extractor.dependencies.python_module_available", return_value=True):
            result = missing_python_packages(["bs4", "ebooklib"])
        assert result == []

    def test_reports_missing_packages(self):
        def fake_available(name):
            return name != "docling"

        with mock.patch("extractor.dependencies.python_module_available", side_effect=fake_available):
            result = missing_python_packages(["docling"])
        assert result == ["docling"]

    def test_maps_module_to_pip_package(self):
        with mock.patch("extractor.dependencies.python_module_available", return_value=False):
            result = missing_python_packages(["bs4"])
        # bs4 maps to beautifulsoup4
        assert result == ["beautifulsoup4"]

    def test_multiple_missing(self):
        with mock.patch("extractor.dependencies.python_module_available", return_value=False):
            result = missing_python_packages(["ebooklib", "bs4"])
        assert result == ["ebooklib", "beautifulsoup4"]


# ═══════════════════════════════════════════════════════════════════════════
#  install_python_packages
# ═══════════════════════════════════════════════════════════════════════════

class TestInstallPythonPackages:
    """Tests for install_python_packages."""

    def test_empty_list_returns_true(self):
        assert install_python_packages([]) is True

    def test_successful_install(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
            result = install_python_packages(["some-package"])

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "some-package" in call_args

    def test_failed_install(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1)
            result = install_python_packages(["bad-package"])

        assert result is False

    def test_exception_during_install(self):
        with mock.patch("subprocess.run", side_effect=OSError("no pip")):
            result = install_python_packages(["pkg"])

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
#  normalize_install_mode
# ═══════════════════════════════════════════════════════════════════════════

class TestNormalizeInstallMode:
    """Tests for normalize_install_mode."""

    def test_no_install_missing_flag(self):
        assert normalize_install_mode(["prog", "--no-install-missing"]) == "no"

    def test_install_missing_yes(self):
        assert normalize_install_mode(["prog", "--install-missing", "yes"]) == "yes"

    def test_install_missing_no(self):
        assert normalize_install_mode(["prog", "--install-missing", "no"]) == "no"

    def test_install_missing_bare(self):
        assert normalize_install_mode(["prog", "--install-missing"]) == "yes"

    def test_env_var_true(self, monkeypatch):
        monkeypatch.setenv("BOOK_SKILL_INSTALL_MISSING", "true")
        assert normalize_install_mode(["prog"]) == "yes"

    def test_env_var_false(self, monkeypatch):
        monkeypatch.setenv("BOOK_SKILL_INSTALL_MISSING", "false")
        assert normalize_install_mode(["prog"]) == "no"

    def test_env_var_ask(self, monkeypatch):
        monkeypatch.setenv("BOOK_SKILL_INSTALL_MISSING", "ask")
        assert normalize_install_mode(["prog"]) == "ask"

    def test_default_is_ask(self, monkeypatch):
        monkeypatch.delenv("BOOK_SKILL_INSTALL_MISSING", raising=False)
        assert normalize_install_mode(["prog"]) == "ask"

    def test_flag_overrides_env(self, monkeypatch):
        monkeypatch.setenv("BOOK_SKILL_INSTALL_MISSING", "yes")
        assert normalize_install_mode(["prog", "--no-install-missing"]) == "no"


# ═══════════════════════════════════════════════════════════════════════════
#  offer_dependency_install
# ═══════════════════════════════════════════════════════════════════════════

class TestOfferDependencyInstall:
    """Tests for offer_dependency_install."""

    def test_does_nothing_if_all_present(self, capsys):
        with mock.patch("extractor.dependencies.missing_python_packages", return_value=[]):
            offer_dependency_install(
                feature="Test",
                module_names=["os"],
                fallback="nothing",
                install_mode="no",
            )
        # Should not print anything since no packages are missing
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_mode_no_uses_fallback(self, capsys):
        with mock.patch("extractor.dependencies.missing_python_packages", return_value=["pkg"]):
            offer_dependency_install(
                feature="Test feature",
                module_names=["missing"],
                fallback="stdlib fallback",
                install_mode="no",
            )
        captured = capsys.readouterr()
        assert "fallback" in captured.out.lower() or "stdlib" in captured.out.lower()

    def test_mode_yes_installs(self, capsys):
        with mock.patch("extractor.dependencies.missing_python_packages", return_value=["pkg"]):
            with mock.patch("extractor.dependencies.install_python_packages", return_value=True) as mock_install:
                with mock.patch("extractor.dependencies.missing_python_packages", side_effect=[["pkg"], []]):
                    offer_dependency_install(
                        feature="Test",
                        module_names=["test_mod"],
                        fallback=None,
                        install_mode="yes",
                    )

    def test_mode_ask_non_interactive_uses_fallback(self, capsys):
        with mock.patch("extractor.dependencies.missing_python_packages", return_value=["pkg"]):
            with mock.patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = False
                offer_dependency_install(
                    feature="Test",
                    module_names=["test_mod"],
                    fallback="a fallback",
                    install_mode="ask",
                )
        captured = capsys.readouterr()
        assert "fallback" in captured.out.lower() or "non-interactive" in captured.out.lower()


# ═══════════════════════════════════════════════════════════════════════════
#  prepare_dependencies
# ═══════════════════════════════════════════════════════════════════════════

class TestPrepareDependencies:
    """Tests for prepare_dependencies dispatch logic."""

    def test_pdf_technical_offers_docling(self):
        with mock.patch("extractor.dependencies.offer_dependency_install") as mock_offer:
            prepare_dependencies(".pdf", "technical", "no")

        # Should have been called with docling
        calls = mock_offer.call_args_list
        features = [c.kwargs["feature"] for c in calls]
        assert any("Technical" in f or "PDF" in f for f in features)

    def test_epub_offers_ebooklib(self):
        with mock.patch("extractor.dependencies.offer_dependency_install") as mock_offer:
            prepare_dependencies(".epub", "text", "no")

        calls = mock_offer.call_args_list
        assert len(calls) >= 1
        module_names = calls[0].kwargs["module_names"]
        assert "ebooklib" in module_names

    def test_html_offers_bs4(self):
        with mock.patch("extractor.dependencies.offer_dependency_install") as mock_offer:
            prepare_dependencies(".html", "text", "no")

        calls = mock_offer.call_args_list
        assert len(calls) >= 1
        module_names = calls[0].kwargs["module_names"]
        assert "bs4" in module_names

    def test_docx_offers_python_docx(self):
        with mock.patch("extractor.dependencies.offer_dependency_install") as mock_offer:
            prepare_dependencies(".docx", "text", "no")

        calls = mock_offer.call_args_list
        assert len(calls) >= 1
        module_names = calls[0].kwargs["module_names"]
        assert "docx" in module_names

    def test_rtf_offers_striprtf(self):
        with mock.patch("extractor.dependencies.offer_dependency_install") as mock_offer:
            prepare_dependencies(".rtf", "text", "no")

        calls = mock_offer.call_args_list
        assert len(calls) >= 1
        module_names = calls[0].kwargs["module_names"]
        assert "striprtf" in module_names

    def test_txt_does_not_offer_anything(self):
        with mock.patch("extractor.dependencies.offer_dependency_install") as mock_offer:
            prepare_dependencies(".txt", "text", "no")

        mock_offer.assert_not_called()

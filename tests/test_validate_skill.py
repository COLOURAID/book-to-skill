"""
Unit tests for tools/validate_skill.py.

Covers:
  - parse_frontmatter
  - get_scalar
  - get_list_items
  - top_level_keys
  - tool_base
  - audit (various valid/invalid SKILL.md scenarios)
  - main (CLI exit codes)
"""

import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from validate_skill import (
    parse_frontmatter,
    get_scalar,
    get_list_items,
    top_level_keys,
    tool_base,
    audit,
    main,
)


# ═══════════════════════════════════════════════════════════════════════════
#  parse_frontmatter
# ═══════════════════════════════════════════════════════════════════════════

class TestParseFrontmatter:
    """Tests for YAML frontmatter extraction."""

    def test_valid_frontmatter(self):
        text = "---\nname: my-skill\ndescription: A test skill\n---\n# Body"
        fm, body = parse_frontmatter(text)
        assert fm is not None
        assert "name: my-skill" in fm
        assert body.strip() == "# Body"

    def test_no_frontmatter(self):
        text = "# Just a heading\nSome content"
        fm, body = parse_frontmatter(text)
        assert fm is None
        assert body is None

    def test_unclosed_frontmatter(self):
        text = "---\nname: broken\nno closing delimiter"
        fm, body = parse_frontmatter(text)
        assert fm is None
        assert body is None

    def test_empty_frontmatter(self):
        text = "---\n---\n# Body"
        fm, body = parse_frontmatter(text)
        assert fm is not None
        assert fm.strip() == ""


# ═══════════════════════════════════════════════════════════════════════════
#  get_scalar
# ═══════════════════════════════════════════════════════════════════════════

class TestGetScalar:
    """Tests for extracting scalar values from frontmatter."""

    def test_simple_value(self):
        fm = "name: my-skill\ndescription: A skill"
        assert get_scalar(fm, "name") == "my-skill"
        assert get_scalar(fm, "description") == "A skill"

    def test_quoted_value(self):
        fm = 'name: "my-skill"\ndescription: \'A skill\''
        assert get_scalar(fm, "name") == "my-skill"
        assert get_scalar(fm, "description") == "A skill"

    def test_missing_key(self):
        fm = "name: my-skill"
        assert get_scalar(fm, "description") is None


# ═══════════════════════════════════════════════════════════════════════════
#  get_list_items
# ═══════════════════════════════════════════════════════════════════════════

class TestGetListItems:
    """Tests for extracting YAML list items."""

    def test_multiline_list(self):
        fm = "allowed-tools:\n  - Bash\n  - Read\n  - Write\nname: test"
        items = get_list_items(fm, "allowed-tools")
        assert items == ["Bash", "Read", "Write"]

    def test_empty_list(self):
        fm = "name: test\ndescription: hi"
        items = get_list_items(fm, "allowed-tools")
        assert items == []

    def test_stops_at_next_key(self):
        fm = "allowed-tools:\n  - Bash\nname: test"
        items = get_list_items(fm, "allowed-tools")
        assert items == ["Bash"]


# ═══════════════════════════════════════════════════════════════════════════
#  top_level_keys
# ═══════════════════════════════════════════════════════════════════════════

class TestTopLevelKeys:
    """Tests for extracting top-level YAML keys."""

    def test_standard_keys(self):
        fm = "name: test\ndescription: hi\nallowed-tools:\n  - Bash"
        keys = top_level_keys(fm)
        assert keys == ["name", "description", "allowed-tools"]

    def test_ignores_list_items(self):
        fm = "name: test\nallowed-tools:\n  - Bash"
        keys = top_level_keys(fm)
        assert "Bash" not in keys


# ═══════════════════════════════════════════════════════════════════════════
#  tool_base
# ═══════════════════════════════════════════════════════════════════════════

class TestToolBase:
    """Tests for tool_base extraction."""

    def test_simple_tool(self):
        assert tool_base("Bash") == "Bash"
        assert tool_base("Read") == "Read"

    def test_parameterized_tool(self):
        assert tool_base("Bash(python3 *)") == "Bash"
        assert tool_base("Bash(npm run test)") == "Bash"


# ═══════════════════════════════════════════════════════════════════════════
#  audit
# ═══════════════════════════════════════════════════════════════════════════

class TestAudit:
    """Tests for the full audit function."""

    def test_valid_skill(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        skill.write_text(textwrap.dedent("""\
            ---
            name: my-test-skill
            description: A valid test skill for unit testing.
            ---
            # My Test Skill

            Some content here.
        """), encoding="utf-8")

        errors, warns = audit(str(skill))
        assert errors == []

    def test_missing_name(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        skill.write_text(textwrap.dedent("""\
            ---
            description: No name here
            ---
            # Content
        """), encoding="utf-8")

        errors, warns = audit(str(skill))
        assert any("name" in e and "missing" in e for e in errors)

    def test_missing_description(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        skill.write_text(textwrap.dedent("""\
            ---
            name: no-desc
            ---
            # Content
        """), encoding="utf-8")

        errors, warns = audit(str(skill))
        assert any("description" in e and "missing" in e for e in errors)

    def test_name_too_long(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        long_name = "a" * 65
        skill.write_text(textwrap.dedent(f"""\
            ---
            name: {long_name}
            description: Test
            ---
            # Content
        """), encoding="utf-8")

        errors, warns = audit(str(skill))
        assert any("64" in e for e in errors)

    def test_name_invalid_chars(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        skill.write_text(textwrap.dedent("""\
            ---
            name: My_Skill!
            description: Bad name
            ---
            # Content
        """), encoding="utf-8")

        errors, warns = audit(str(skill))
        assert any("lowercase" in e or "must be" in e for e in errors)

    def test_reserved_name(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        skill.write_text(textwrap.dedent("""\
            ---
            name: claude-helper
            description: Uses reserved word
            ---
            # Content
        """), encoding="utf-8")

        errors, warns = audit(str(skill))
        assert any("reserved" in e for e in errors)

    def test_no_frontmatter(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        skill.write_text("# Just markdown\nNo frontmatter at all.", encoding="utf-8")

        errors, warns = audit(str(skill))
        assert any("frontmatter" in e for e in errors)

    def test_unrecognized_keys_warn(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        skill.write_text(textwrap.dedent("""\
            ---
            name: test-skill
            description: A skill
            shell_command: echo hi
            ---
            # Content
        """), encoding="utf-8")

        errors, warns = audit(str(skill))
        assert errors == []
        assert any("shell_command" in w for w in warns)

    def test_allowed_tools_missing_bash(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        skill.write_text(textwrap.dedent("""\
            ---
            name: test-skill
            description: A skill
            allowed-tools:
              - Read
              - Write
            ---
            Run this:
            ```bash
            echo "hello"
            ```
        """), encoding="utf-8")

        errors, warns = audit(str(skill))
        assert any("Bash" in e for e in errors)

    def test_description_too_long(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        long_desc = "x" * 1025
        skill.write_text(textwrap.dedent(f"""\
            ---
            name: test-skill
            description: {long_desc}
            ---
            # Content
        """), encoding="utf-8")

        errors, warns = audit(str(skill))
        assert any("1024" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════
#  main (CLI)
# ═══════════════════════════════════════════════════════════════════════════

class TestMain:
    """Tests for the CLI entry point."""

    def test_exits_1_on_errors(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        skill.write_text("# No frontmatter", encoding="utf-8")

        with mock.patch("sys.argv", ["validate_skill.py", str(skill)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_exits_0_on_valid(self, tmp_path):
        skill = tmp_path / "SKILL.md"
        skill.write_text(textwrap.dedent("""\
            ---
            name: good-skill
            description: A perfectly valid skill.
            ---
            # Good Skill
        """), encoding="utf-8")

        with mock.patch("sys.argv", ["validate_skill.py", str(skill)]):
            # Should not raise
            main()

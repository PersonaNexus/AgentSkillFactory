"""Tests for utility functions."""

from __future__ import annotations

from agentforge.utils import safe_filename, safe_output_path


class TestSafeFilename:
    def test_normal_filename(self):
        assert safe_filename("agt_data_engineer_001") == "agt_data_engineer_001"

    def test_with_extension(self):
        assert safe_filename("agent.yaml") == "agent.yaml"

    def test_path_traversal_stripped(self):
        result = safe_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_backslash_stripped(self):
        result = safe_filename("..\\..\\windows\\system32")
        assert "\\" not in result

    def test_special_characters(self):
        result = safe_filename("agent@name!#$%")
        assert "@" not in result
        assert "!" not in result

    def test_empty_fallback(self):
        assert safe_filename("") == "unnamed_agent"
        assert safe_filename("../..") == "unnamed_agent"

    def test_collapse_underscores(self):
        result = safe_filename("a___b___c")
        assert result == "a_b_c"

    def test_preserves_hyphens(self):
        assert safe_filename("my-agent-v2") == "my-agent-v2"


class TestSafeOutputPath:
    def test_normal_path(self, tmp_path):
        result = safe_output_path(tmp_path, "agent.yaml")
        assert result == tmp_path / "agent.yaml"
        assert result.is_relative_to(tmp_path.resolve())

    def test_path_traversal_blocked(self, tmp_path):
        # safe_filename strips the traversal characters, so this should be safe
        result = safe_output_path(tmp_path, "../../etc/passwd.yaml")
        assert result.is_relative_to(tmp_path.resolve())

    def test_safe_name_used(self, tmp_path):
        result = safe_output_path(tmp_path, "bad@name!.yaml")
        assert "@" not in str(result)

    def test_prefix_sibling_not_considered_inside(self, tmp_path):
        """relative_to rejects same-prefix siblings (startswith bug)."""
        from agentforge.utils import _is_within

        base = tmp_path / "out"
        sibling = tmp_path / "out_evil" / "x"
        base.mkdir()
        sibling.parent.mkdir()
        sibling.write_text("x")
        assert _is_within(base.resolve(), (base / "a").resolve())
        assert not _is_within(base.resolve(), sibling.resolve())

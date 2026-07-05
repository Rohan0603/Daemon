"""Tests for Phase 4 Task 4.2 XML prompt builders.

Verifies build_static_block, build_dynamic_block, and _xml_escape
from src.llm.context_manager.
"""
import pytest


def test_xml_escape_ampersand():
    from src.llm.context_manager import _xml_escape
    assert _xml_escape("A&B") == "A&amp;B"


def test_xml_escape_angle_brackets():
    from src.llm.context_manager import _xml_escape
    assert _xml_escape("<test>") == "&lt;test&gt;"


def test_xml_escape_no_change():
    from src.llm.context_manager import _xml_escape
    assert _xml_escape("plain text 123") == "plain text 123"


def test_build_static_block_basic():
    from src.llm.context_manager import build_static_block
    result = build_static_block(mode="chat", apm=42, idle_seconds=10.5, persona="Kenny")
    assert "<static>" in result
    assert "</static>" in result
    assert "<mode>chat</mode>" in result
    assert "<apm>42</apm>" in result
    assert "<idle_seconds>10</idle_seconds>" in result
    assert "<persona>Kenny</persona>" in result


def test_build_static_block_no_persona():
    from src.llm.context_manager import build_static_block
    result = build_static_block(mode="auto", apm=0, persona="")
    assert "<persona>" not in result


def test_build_dynamic_block_empty():
    """Empty dynamic block should return empty string."""
    from src.llm.context_manager import build_dynamic_block
    result = build_dynamic_block()
    assert result == ""


def test_build_dynamic_block_user_input():
    from src.llm.context_manager import build_dynamic_block
    result = build_dynamic_block(user_input="Hello, Kenny!")
    assert "<dynamic>" in result
    assert "</dynamic>" in result
    assert "<user_input>Hello, Kenny!</user_input>" in result


def test_build_dynamic_block_all_fields():
    from src.llm.context_manager import build_dynamic_block
    result = build_dynamic_block(
        user_input="hi",
        typing_content="def foo(): pass",
        screen_text="VSCode - main.py"
    )
    assert "<user_input>hi</user_input>" in result
    assert "<typing>def foo(): pass</typing>" in result
    assert "<screen>VSCode - main.py</screen>" in result


def test_build_dynamic_block_xss_escape():
    """XML special chars in dynamic fields must be escaped."""
    from src.llm.context_manager import build_dynamic_block
    result = build_dynamic_block(user_input="<script>alert('xss')</script>")
    assert "&lt;script&gt;alert('xss')&lt;/script&gt;" in result
    assert "<script>" not in result


def test_build_dynamic_block_truncation():
    """Fields over _XML_TRUNCATE (1500) chars should be truncated."""
    from src.llm.context_manager import build_dynamic_block
    long_text = "x" * 2000
    result = build_dynamic_block(typing_content=long_text)
    # Expect truncated content inside <typing> tag
    assert len(result) < 1700  # overhead from tags
    assert "x" * 1500 in result
    assert "x" * 2000 not in result


def test_static_block_escapes_xml():
    """If persona contains XML-unsafe chars, they should be escaped."""
    from src.llm.context_manager import build_static_block
    result = build_static_block(mode="test", apm=5, persona="Kenny<3")
    assert "<persona>Kenny&lt;3</persona>" in result

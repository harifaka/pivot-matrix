from __future__ import annotations

from pivot.ui.markdown import sanitize_markdown


def test_markdown_sanitization_removes_html_and_script_blocks() -> None:
    raw = "<script>alert(1)</script><b>Hello</b> world"
    sanitized = sanitize_markdown(raw)
    assert "<script>" not in sanitized
    assert "<b>" not in sanitized
    assert "Hello world" in sanitized


def test_markdown_sanitization_rewrites_javascript_links() -> None:
    raw = "[click](javascript:alert('xss'))"
    sanitized = sanitize_markdown(raw)
    assert "javascript:" not in sanitized.casefold()
    assert "(#)" in sanitized

"""Markdown sanitization helpers."""

from __future__ import annotations

import re

SCRIPT_BLOCK_PATTERN = re.compile(r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
JAVASCRIPT_LINK_PATTERN = re.compile(r"\((\s*javascript:[^)]+)\)", re.IGNORECASE)


def sanitize_markdown(markdown: str) -> str:
    sanitized = SCRIPT_BLOCK_PATTERN.sub("", markdown)
    sanitized = HTML_TAG_PATTERN.sub("", sanitized)
    sanitized = JAVASCRIPT_LINK_PATTERN.sub("(#)", sanitized)
    return sanitized

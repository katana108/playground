"""Shared helpers for Anthropic API calls."""

from __future__ import annotations

from typing import Any

MODEL_DEFAULT = "claude-sonnet-4-6"


def llm_text(response: Any, fallback: str = "") -> str:
    """Safely extract text from an Anthropic response.

    response.content[0].text crashes when the API returns an error block,
    a tool_use block, or an empty list. This helper returns the first text
    block it finds, or fallback if there is none.
    """
    for block in getattr(response, "content", []):
        if hasattr(block, "text") and block.text:
            return block.text.strip()
    return fallback

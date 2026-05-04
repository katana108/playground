"""Web-backed research service for Sofico."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import anthropic

from llm_utils import MODEL_DEFAULT


class ResearchService:
    """Run bounded external research queries with Sofico-style synthesis."""

    def __init__(self, model: str = MODEL_DEFAULT):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def research(
        self,
        *,
        user_message: str,
        learner_context: str = "",
        topic_hint: str = "",
        document_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Research a learner request and return a grounded synthesis."""
        if not os.getenv("ANTHROPIC_API_KEY"):
            return {
                "status": "error",
                "message": "Research is not configured in this runtime yet because the Anthropic API key is missing.",
            }

        doc_block = ""
        if document_context:
            doc_block = f"""
Saved document context:
- title: {document_context.get("title", "")}
- topic: {document_context.get("topic", "")}
- doc_type: {document_context.get("doc_type", "")}
- authors: {", ".join(document_context.get("authors", []) or [])}
- year: {document_context.get("year", "")}
- summary_short: {document_context.get("summary_short", "")}
- saved_notes_excerpt:
{str(document_context.get("notes", "") or "")[:2500]}

If the learner's request refers to this saved document, use it as a seed and explicitly separate:
1. what the saved document says
2. what newer or external sources add or challenge
"""

        prompt = f"""
You are Sofico doing research for a learner.

Learner request:
{user_message}

Learner context:
{learner_context or "No extra learner context provided."}

Topic hint:
{topic_hint or "None"}

{doc_block}

Use web search to answer the request.

Requirements:
- Be direct and helpful.
- If the learner asked for current or external sources, actually use web search.
- If a saved document was provided, distinguish saved-document claims from external research.
- End with a short "Sources to inspect next" section listing 3-5 concrete items or search directions.
- Do not mention backend tools or JSON.
""".strip()

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2500,
                tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 8}],
                messages=[{"role": "user", "content": prompt}],
            )
            text = self._extract_final_synthesis(response.content)
            return {
                "status": "ok",
                "message": text or "I could not assemble a useful research summary from the current search results.",
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": f"I hit a research runtime error: {exc}",
            }

    @staticmethod
    def _extract_final_synthesis(content) -> str:
        """Return only the synthesis text after the last tool call.

        Web search responses interleave Claude's planning narration with
        tool_use and tool_result blocks. The user-facing answer is the text
        emitted after the final tool result; earlier text blocks are
        chain-of-thought ("Let me search...", "Now I have enough...") and
        must not leak to learners.
        """
        last_tool_idx = -1
        for idx, block in enumerate(content):
            block_type = getattr(block, "type", "")
            if block_type in {"server_tool_use", "web_search_tool_result", "tool_use", "tool_result"}:
                last_tool_idx = idx

        tail = content[last_tool_idx + 1:] if last_tool_idx >= 0 else content
        return "\n\n".join(
            block.text for block in tail if hasattr(block, "text") and block.text
        ).strip()

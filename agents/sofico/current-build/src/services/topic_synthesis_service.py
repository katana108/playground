"""Topic-scoped cross-document synthesis for Sofico."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from llm_utils import llm_text
from services.topic_corpus_service import TopicCorpus


class TopicSynthesisService:
    """Synthesize patterns and tensions across multiple saved papers in one topic."""

    def __init__(self, session_response_service: Any):
        self.response_service = session_response_service
        self.client = getattr(session_response_service, "client", None)
        self.model = getattr(session_response_service, "model", "claude-sonnet-4-6")

    def synthesize(
        self,
        *,
        topic: str,
        corpus: TopicCorpus,
        user_message: str,
        learner_context: str = "",
    ) -> Dict[str, Any]:
        """Return a topic-scoped synthesis grounded only in saved documents."""
        if corpus.document_count < 2:
            return {
                "status": "not_enough_documents",
                "message": f"I need at least two saved papers under *{topic}* before I can compare patterns across them.",
            }
        if not self.client or not os.getenv("ANTHROPIC_API_KEY"):
            return {
                "status": "error",
                "message": "Topic synthesis is not configured in this runtime yet because the Anthropic API key is missing.",
            }

        documents_block = []
        for index, document in enumerate(corpus.documents[:8], start=1):
            documents_block.append(
                f"""Document {index}
- title: {document.title}
- authors: {", ".join(document.authors) if document.authors else "unknown"}
- year: {document.year or ""}
- doc_type: {document.doc_type or "document"}
- summary_short: {document.summary_short}
- question_count: {len(document.questions)}
- notes_excerpt:
{document.notes[:2200]}"""
            )

        prompt = f"""
You are Sofico synthesizing across a saved learner topic.

Learner request:
{user_message}

Topic:
{topic}

Learner context:
{learner_context or "No extra learner context provided."}

Saved documents in this topic:
{chr(10).join(documents_block)}

Requirements:
- Use only the saved documents provided here.
- Do not pretend you searched the web.
- Explain the strongest recurring themes across the papers.
- Highlight agreements, tensions, and surprising connections.
- Name missing links or open questions when the papers leave gaps.
- End with a short "Good next study moves" section.
- Be concrete and reference document titles when useful.
""".strip()

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = llm_text(response)
            if text and getattr(response, "stop_reason", "") == "max_tokens":
                text = f"{text.rstrip()}\n\n_…I had more to say but ran out of room. Say *continue* and I'll keep going._"
            return {
                "status": "ok",
                "message": text or f"I could not synthesize a useful cross-document answer for *{topic}* just now.",
                "document_count": corpus.document_count,
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": f"I hit a topic-synthesis runtime error: {exc}",
            }


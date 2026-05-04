"""Executor for topic-scoped multi-document synthesis."""

from __future__ import annotations

from ..reflection_engine import SessionReflectionInput
from .base import ExecutionResult


class TopicSynthesisExecutor:
    """Synthesize patterns across all saved documents in one topic."""

    capability_name = "synthesize_topic"

    def execute(self, ctx, decision):
        corpus_service = getattr(ctx, "topic_corpus_service", None)
        synthesis_service = getattr(ctx, "topic_synthesis_service", None)
        if not corpus_service or not synthesis_service:
            return ExecutionResult(
                capability=self.capability_name,
                messages=["I know this topic-synthesis capability exists, but the topic services are not wired in this runtime yet."],
                messages_recorded=False,
            )

        topic = self._resolve_topic(ctx, decision, corpus_service)
        if not topic:
            return ExecutionResult(
                capability=self.capability_name,
                messages=["Tell me which topic to synthesize. For example: `find connections between all papers in consciousness`."],
                messages_recorded=False,
            )

        corpus = corpus_service.load_corpus(ctx.turn.user_id, topic)
        learner_context = ctx.hooks.recall_recent_context() if ctx.hooks else ""
        result = synthesis_service.synthesize(
            topic=topic,
            corpus=corpus,
            user_message=ctx.turn.message,
            learner_context=learner_context,
        )
        reflection_input = None
        if result.get("status") == "ok":
            reflection_input = SessionReflectionInput(
                user_id=ctx.turn.user_id,
                summary=f"The learner explored cross-document synthesis inside the topic {topic}.",
                observations=[f"They are connecting ideas across {corpus.document_count} saved documents."],
                progress_notes=[f"Worked across the full {topic} topic corpus."],
            )

        return ExecutionResult(
            capability=self.capability_name,
            messages=[result.get("message") or f"I couldn't synthesize the {topic} topic just now."],
            messages_recorded=False,
            reflection_input=reflection_input,
            state_delta={
                "focus": {
                    "kind": "topic",
                    "topic": topic,
                    "source_message": ctx.turn.message[:200],
                    "metadata": {"manually_set": True},
                },
                "activity": {
                    "kind": "topic_synthesis",
                    "summary": f"Synthesized patterns across saved documents in {topic}.",
                    "topic": topic,
                },
            },
            metadata={
                "topic_synthesis": {
                    "status": result.get("status"),
                    "topic": topic,
                    "document_count": corpus.document_count,
                    "question_count": corpus.question_count,
                }
            },
        )

    def _resolve_topic(self, ctx, decision, corpus_service) -> str:
        """Resolve a topic from interpreter hints, focus, or raw words."""
        target = dict(getattr(decision, "target", {}) or {})
        hinted = str(target.get("topic") or "").strip()
        if hinted:
            return corpus_service.resolve_topic(ctx.turn.user_id, hinted)
        focus_topic = str(ctx.state.current_focus.topic or "").strip()
        if focus_topic:
            lowered = ctx.turn.message.lower()
            if any(token in lowered for token in ("this topic", "these papers", "this folder", "them")):
                return focus_topic
        available = list(ctx.data_service.get_available_topics(ctx.turn.user_id) or [])
        lowered = ctx.turn.message.lower()
        for topic in available:
            normalized = topic.lower().replace("-", " ").replace("_", " ")
            if topic.lower() in lowered or normalized in lowered:
                return topic
        return ""

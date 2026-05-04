"""Executor for reindex/repair/dedupe maintenance turns."""

from __future__ import annotations

from .base import ExecutionResult


class LibraryMaintenanceExecutor:
    """Repair topic indexes and dedupe safe duplicate artifacts."""

    capability_name = "repair_library"

    def execute(self, ctx, decision):
        service = getattr(ctx, "library_maintenance_service", None)
        corpus_service = getattr(ctx, "topic_corpus_service", None)
        if not service:
            return ExecutionResult(
                capability=self.capability_name,
                messages=["I know this maintenance capability exists, but the repair service is not wired in this runtime yet."],
                messages_recorded=False,
            )

        target = dict(getattr(decision, "target", {}) or {})
        hinted_topic = str(target.get("topic") or "").strip()
        topic = corpus_service.resolve_topic(ctx.turn.user_id, hinted_topic) if (corpus_service and hinted_topic) else ""
        result = service.repair_library(ctx.turn.user_id, topic=topic)
        state_delta = {}
        if topic:
            state_delta = {
                "focus": {
                    "kind": "topic",
                    "topic": topic,
                    "source_message": ctx.turn.message[:200],
                    "metadata": {"manually_set": True},
                },
                "activity": {
                    "kind": "library_repair",
                    "summary": f"Repaired saved document state for {topic}.",
                    "topic": topic,
                },
            }
        return ExecutionResult(
            capability=self.capability_name,
            messages=[result.get("message") or "I couldn't repair the library just now."],
            messages_recorded=False,
            state_delta=state_delta,
            metadata={"library_repair": result},
        )

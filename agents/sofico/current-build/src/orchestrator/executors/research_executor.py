"""Executor for external-source research turns."""

from __future__ import annotations

from .base import ExecutionResult


class ResearchExecutor:
    """Run bounded external research, optionally scoped by a saved document."""

    capability_name = "research"

    def execute(self, ctx, decision):
        resolver = ctx.document_resolver_service
        service = ctx.research_service
        if not service:
            return ExecutionResult(
                capability=self.capability_name,
                messages=["I know this capability exists, but the research service is not wired in this runtime yet."],
                messages_recorded=False,
            )

        artifact = None
        if resolver:
            artifact = resolver.select_document_artifact(
                resolver.matching_artifacts(ctx.turn.user_id, ctx.turn.message)
            )
            if not artifact:
                artifact = resolver.focused_artifact(ctx.turn.user_id, ctx.state.current_focus)

        learner_context = ctx.hooks.recall_recent_context() if ctx.hooks else ""
        document_context = None
        topic_hint = ""
        if artifact and resolver:
            doc_id = str((artifact.metadata or {}).get("doc_id", "") or "").strip()
            manifest = ctx.data_service.get_document_manifest(ctx.turn.user_id, doc_id) if doc_id else {}
            notes = ""
            if doc_id and hasattr(ctx.data_service, "get_document_notes"):
                notes = ctx.data_service.get_document_notes(ctx.turn.user_id, doc_id) or ""
            topic_hint = artifact.topic or ctx.state.current_focus.topic or ""
            document_context = {
                "title": resolver.artifact_title(artifact),
                "topic": artifact.topic,
                "doc_type": str((artifact.metadata or {}).get("doc_type", "") or ""),
                "authors": list((artifact.metadata or {}).get("authors", []) or []),
                "year": (artifact.metadata or {}).get("year"),
                "summary_short": (((manifest.get("learning") or {}).get("summary_short")) or ""),
                "notes": notes,
            }
        else:
            topic_hint = ctx.state.current_focus.topic or str((decision.target or {}).get("topic") or "")

        result = service.research(
            user_message=ctx.turn.message,
            learner_context=learner_context,
            topic_hint=topic_hint,
            document_context=document_context,
        )

        return ExecutionResult(
            capability=self.capability_name,
            messages=[result.get("message") or "I couldn't assemble a useful research answer."],
            messages_recorded=False,
            metadata={"research": result},
        )

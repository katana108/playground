"""Executor for ingest/material processing turns."""

from __future__ import annotations

from ..reflection_engine import SessionReflectionInput
from .base import ExecutionResult


class IngestExecutor:
    """Process pasted study material or start buffered capture."""

    capability_name = "ingest_material"

    def execute(self, ctx, decision):
        if ctx.hooks.should_auto_capture(ctx.turn.message, self.capability_name):
            inferred_intent = ctx.hooks.infer_capture_intent(ctx.turn.message)
            outputs = ctx.hooks.start_capture(
                inferred_intent,
                ctx.turn.message,
                [ctx.turn.message],
            )
            return ExecutionResult(
                capability=self.capability_name,
                messages=outputs,
                messages_recorded=False,
            )

        followup = "explain" if ctx.hooks.infer_capture_intent(ctx.turn.message) == "explain" else None
        outputs = ctx.hooks.execute_ingest(ctx.turn.message, requested_followup=followup)

        reflection_input = self._build_reflection_input(ctx)

        return ExecutionResult(
            capability=self.capability_name,
            messages=outputs,
            reflection_input=reflection_input,
            messages_recorded=True,
        )

    def _build_reflection_input(self, ctx) -> SessionReflectionInput | None:
        ingest_result = (ctx.state.metadata or {}).get("last_ingest_result") or {}
        if ingest_result.get("status") != "saved":
            return None

        topic = ingest_result.get("topic", "")
        doc_name = ingest_result.get("doc_name", "")
        question_count = int(ingest_result.get("question_count", 0) or 0)
        summary = f"The learner added study material on {topic or 'a new topic'}."
        progress_notes = [f"Saved {doc_name or 'new material'} under {topic or 'a topic'}."]
        if question_count:
            progress_notes.append(f"Generated {question_count} review questions from that material.")

        return SessionReflectionInput(
            user_id=ctx.turn.user_id,
            summary=summary,
            observations=[f"The learner is actively building a study set around {topic or doc_name or 'a topic'}."],
            progress_notes=progress_notes,
        )

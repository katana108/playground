"""Executor for pending upload confirmation turns."""

from __future__ import annotations

from ..reflection_engine import SessionReflectionInput
from .base import ExecutionResult


class UploadConfirmationExecutor:
    """Resolve yes/no/folder-name turns for pending upload saves."""

    capability_name = "upload_confirmation"

    def execute(self, ctx, decision):
        outputs = ctx.hooks.handle_pending_ingest_confirmation(ctx.turn.message)

        reflection_input = None
        if (
            not ctx.upload_handler.has_pending(ctx.turn.user_id)
            and (ctx.state.metadata or {}).get("last_activity_kind") == "ingest"
            and (ctx.state.metadata or {}).get("last_activity_topic")
        ):
            topic = ctx.state.metadata.get("last_activity_topic", "")
            summary = f"The learner finished saving pending study material under {topic}."
            reflection_input = SessionReflectionInput(
                user_id=ctx.turn.user_id,
                summary=summary,
                observations=[f"The learner is actively gathering study material about {topic}."],
                progress_notes=[summary],
            )

        return ExecutionResult(
            capability=self.capability_name,
            messages=outputs,
            reflection_input=reflection_input,
            messages_recorded=True,
        )

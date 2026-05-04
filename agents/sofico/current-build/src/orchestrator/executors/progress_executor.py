"""Executor for progress-report turns."""

from __future__ import annotations

from .base import ExecutionResult


class ProgressExecutor:
    """Run the existing progress handler through the executor contract."""

    capability_name = "show_progress"

    def execute(self, ctx, decision):
        if ctx.progress_handler is None:
            return ExecutionResult(
                capability=self.capability_name,
                messages=["Progress reporting is not configured in this runtime yet."],
                messages_recorded=False,
            )

        outputs = []
        ctx.progress_handler.handle(
            {"user": ctx.turn.user_id, "text": ctx.turn.message},
            lambda message, **_: outputs.append(message),
        )
        return ExecutionResult(
            capability=self.capability_name,
            messages=outputs,
            messages_recorded=False,
        )

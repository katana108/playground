"""Executor for artifact listing turns."""

from __future__ import annotations

from .base import ExecutionResult


class ArtifactExecutor:
    """Show saved notes, questions, and uploaded materials."""

    capability_name = "show_artifacts"

    def execute(self, ctx, decision):
        outputs = ctx.hooks.show_artifacts(ctx.turn.message)
        return ExecutionResult(
            capability=self.capability_name,
            messages=outputs,
            messages_recorded=False,
        )

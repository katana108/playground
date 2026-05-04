"""Executor for recent-context recall turns."""

from __future__ import annotations

from .base import ExecutionResult


class RecallExecutor:
    """Answer what the learner and Sofico were doing recently."""

    capability_name = "recall_context"

    def execute(self, ctx, decision):
        intent = str(getattr(decision, "intent", "") or "")
        output = ctx.hooks.recall_recent_context(intent=intent)
        return ExecutionResult(
            capability=self.capability_name,
            messages=[output],
            messages_recorded=False,
        )

"""Executor for curriculum / study-plan turns."""

from __future__ import annotations

import re

from .base import ExecutionResult


class PlanExecutor:
    """Start or continue the curriculum handler through the executor loop."""

    capability_name = "plan_study"

    def execute(self, ctx, decision):
        if ctx.curriculum_handler is None:
            return ExecutionResult(
                capability=self.capability_name,
                messages=["Study planning is not configured in this runtime yet."],
                messages_recorded=False,
            )

        outputs = []
        user_id = ctx.turn.user_id
        message = ctx.turn.message

        if ctx.curriculum_handler.is_active(user_id):
            ctx.curriculum_handler.handle(
                user_id,
                message,
                lambda text, **_: outputs.append(text),
            )
            return ExecutionResult(
                capability=self.capability_name,
                messages=outputs,
                messages_recorded=False,
            )

        subject = self._extract_subject(message)
        if not subject:
            outputs.append("What subject do you want to build a study plan for?")
        else:
            ctx.curriculum_handler.start(
                user_id,
                subject,
                lambda text, **_: outputs.append(text),
            )

        return ExecutionResult(
            capability=self.capability_name,
            messages=outputs,
            messages_recorded=False,
        )

    def _extract_subject(self, message: str) -> str:
        """Pull the likely study subject out of a planning request."""
        text = message.strip()
        lowered = text.lower()
        prefixes = (
            "study plan for ",
            "curriculum for ",
            "plan my study for ",
            "make me a plan for ",
            "build a curriculum on ",
            "build a curriculum for ",
            "teach me ",
        )
        for prefix in prefixes:
            if lowered.startswith(prefix):
                return text[len(prefix):].strip(" .?!")

        match = re.search(r"\b(?:for|on)\s+(.+)$", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" .?!")
        return ""

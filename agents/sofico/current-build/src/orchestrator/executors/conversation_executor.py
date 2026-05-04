"""Executors for explain/converse turns."""

from __future__ import annotations

from ..reflection_engine import SessionReflectionInput
from .base import ExecutionResult


class ConversationExecutor:
    """Handle explain and converse capabilities through one shared path."""

    capability_name = "converse"

    def execute(self, ctx, decision):
        capability = decision.capability or self.capability_name
        user_id = ctx.turn.user_id

        if ctx.explanation_handler.is_active(user_id) and not ctx.hooks.should_escape_active_explanation(ctx.turn.message, decision.target):
            outputs = ctx.hooks.handle_active_explanation(ctx.turn.message)
            reflection_input = None
            if hasattr(ctx.explanation_handler, "take_last_completed_explanation"):
                completed = ctx.explanation_handler.take_last_completed_explanation(user_id)
                if completed:
                    reflection_input = self._build_explanation_reflection(user_id, completed)
            return ExecutionResult(
                capability=capability,
                messages=outputs,
                reflection_input=reflection_input,
                messages_recorded=True,
            )

        document_answer = ctx.hooks.try_answer_from_matching_document(
            ctx.turn.message,
            capability,
            {
                "capability": decision.capability,
                "intent": decision.intent,
                "target": decision.target,
            },
            ctx.bootstrap,
        )
        if document_answer:
            return ExecutionResult(
                capability=capability,
                messages=document_answer,
                messages_recorded=True,
            )

        llm_confident = decision.source == "llm" and decision.confidence >= 0.6
        ingest_intent = decision.intent in {"save_new_material", "ingest_material", "paste_content"}

        if not (llm_confident and not ingest_intent):
            if ctx.hooks.should_start_capture(ctx.turn.message, capability):
                outputs = ctx.hooks.start_capture("explain", ctx.turn.message, None)
                return ExecutionResult(
                    capability=capability,
                    messages=outputs,
                    messages_recorded=False,
                )

            if ctx.hooks.should_auto_capture(ctx.turn.message, capability):
                inferred_intent = "explain" if capability == "explain" else "ingest_material"
                outputs = ctx.hooks.start_capture(
                    inferred_intent,
                    ctx.turn.message,
                    [ctx.turn.message],
                )
                return ExecutionResult(
                    capability=capability,
                    messages=outputs,
                    messages_recorded=False,
                )

        if capability == "explain":
            explanation_outputs = ctx.hooks.try_start_explanation(ctx.turn.message, decision.target)
            if explanation_outputs:
                return ExecutionResult(
                    capability=capability,
                    messages=explanation_outputs,
                    messages_recorded=True,
                )

        if capability == "converse" and ctx.hooks.should_continue_from_focus(ctx.turn.message):
            explanation_outputs = ctx.hooks.try_start_explanation(ctx.turn.message, decision.target)
            if explanation_outputs:
                return ExecutionResult(
                    capability=capability,
                    messages=explanation_outputs,
                    messages_recorded=True,
                )

        ctx.hooks.refresh_focus_from_message(ctx.turn.message)
        reply = ctx.hooks.compose_teacher_reply(ctx.turn.message, capability, ctx.bootstrap)
        return ExecutionResult(
            capability=capability,
            messages=[reply],
            messages_recorded=True,
        )

    def _build_explanation_reflection(self, user_id: str, session: dict) -> SessionReflectionInput | None:
        topic = session.get("topic", "")
        history = session.get("history", []) or []
        learner_turns = sum(1 for item in history if item.get("role") == "user")
        if not topic:
            return None

        observations = [f"The learner engaged in an explanation session on {topic}."]
        if learner_turns > 2:
            observations.append(f"They asked multiple follow-up questions while learning {topic}.")

        return SessionReflectionInput(
            user_id=user_id,
            summary=f"The learner completed an explanation walkthrough on {topic}.",
            observations=observations,
            progress_notes=[f"Worked through {topic} in explanation mode."],
        )

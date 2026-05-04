"""Executor for quiz/review capability turns."""

from __future__ import annotations

from ..reflection_engine import SessionReflectionInput
from .base import ExecutionResult


class ReviewExecutor:
    """Start or continue a review session."""

    capability_name = "review"

    def execute(self, ctx, decision):
        user_id = ctx.turn.user_id
        active = user_id in ctx.study_handler.active_sessions

        if active:
            if ctx.hooks.is_review_restart_request(ctx.turn.message):
                ctx.study_handler.cancel_session(user_id)
                outputs = ctx.hooks.start_review_session(ctx.turn.message)
            elif not ctx.hooks.should_escape_active_review(ctx.turn.message):
                outputs = ctx.hooks.handle_active_review(ctx.turn.message)
            else:
                outputs = ctx.hooks.start_review_session(ctx.turn.message)
        else:
            outputs = ctx.hooks.start_review_session(ctx.turn.message)

        reflection_input = None
        if hasattr(ctx.study_handler, "take_last_completed_session"):
            completed = ctx.study_handler.take_last_completed_session(user_id)
            if completed:
                reflection_input = self._build_reflection_input(user_id, completed)

        return ExecutionResult(
            capability=self.capability_name,
            messages=outputs,
            reflection_input=reflection_input,
            messages_recorded=True,
        )

    def _build_reflection_input(self, user_id: str, session: dict) -> SessionReflectionInput | None:
        questions = session.get("questions", []) or []
        results = session.get("results", []) or []
        graded = [r for r in results if not r.get("skipped") and r.get("score") is not None]
        if not questions:
            return None

        topics = sorted({q.get("topic", "") for q in questions if q.get("topic")})
        topic_text = ", ".join(topics) if topics else "their current materials"
        avg_score = (
            sum(float(r.get("score", 0)) for r in graded) / len(graded)
            if graded else 0.0
        )

        progress_notes = [
            f"Completed a review session on {topic_text}.",
            f"Average review score was {avg_score:.1f}/5.",
        ]
        observations = [
            f"The learner stayed engaged through {len(results)} review items."
        ]
        if avg_score >= 4:
            progress_notes.append(f"They are showing strong recall in {topic_text}.")
        elif graded:
            progress_notes.append(f"They still need reinforcement in parts of {topic_text}.")

        return SessionReflectionInput(
            user_id=user_id,
            summary=f"The learner completed a quiz session on {topic_text}.",
            observations=observations,
            progress_notes=progress_notes,
        )

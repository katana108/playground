"""Executor for regenerating notes/questions from existing saved documents."""

from __future__ import annotations

from ..reflection_engine import SessionReflectionInput
from .base import ExecutionResult


class StudyArtifactsExecutor:
    """Refresh saved study artifacts for an existing document."""

    capability_name = "create_study_artifacts"

    def execute(self, ctx, decision):
        resolver = ctx.document_resolver_service
        service = ctx.artifact_generation_service
        if not resolver or not service:
            return ExecutionResult(
                capability=self.capability_name,
                messages=["I know this capability exists, but the artifact-generation service is not wired in this runtime yet."],
                messages_recorded=False,
            )

        artifact = resolver.select_document_artifact(
            resolver.matching_artifacts(ctx.turn.user_id, ctx.turn.message)
        )
        if not artifact:
            artifact = resolver.focused_artifact(ctx.turn.user_id, ctx.state.current_focus)

        if not artifact:
            return ExecutionResult(
                capability=self.capability_name,
                messages=["Tell me which saved paper or document to refresh first. For example: `regenerate notes for Ward` or `make questions for this paper`."],
                messages_recorded=False,
            )

        regenerate_notes, regenerate_questions = self._requested_outputs(decision.intent)
        result = service.regenerate_for_artifact(
            ctx.turn.user_id,
            artifact,
            regenerate_notes=regenerate_notes,
            regenerate_questions=regenerate_questions,
        )
        message = result.get("message") or "I couldn't refresh that study material."
        reflection_input = None
        if result.get("status") == "saved":
            reflection_input = SessionReflectionInput(
                user_id=ctx.turn.user_id,
                summary=f"The learner refreshed study artifacts for {resolver.artifact_title(artifact)}.",
                observations=[f"They are iterating on saved material for {artifact.topic or resolver.artifact_title(artifact)}."],
                progress_notes=[message],
            )
        return ExecutionResult(
            capability=self.capability_name,
            messages=[message],
            reflection_input=reflection_input,
            messages_recorded=False,
            metadata={
                "artifact_generation": result,
            },
        )

    def _requested_outputs(self, intent: str) -> tuple[bool, bool]:
        """Decide which artifacts to regenerate from the LLM-supplied intent."""
        if "notes" in intent or "summary" in intent:
            return True, False
        if "question" in intent or "quiz" in intent or "card" in intent:
            return False, True
        return True, True

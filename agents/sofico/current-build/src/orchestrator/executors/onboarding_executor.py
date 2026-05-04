"""Executor for the Sofico onboarding capability."""

from __future__ import annotations

from .base import ExecutionResult


class OnboardingExecutor:
    """Run the short structured onboarding workflow."""

    capability_name = "onboard_user"

    def execute(self, ctx, decision):
        model = ctx.bootstrap.student_model
        if not ctx.onboarding_flow.needs_onboarding(model):
            name = (
                (model.identity or {}).get("preferred_form_of_address")
                or (model.identity or {}).get("learner_name")
                or "there"
            )
            reply = f"Welcome back, {name}. I already have your learner profile loaded."
            ctx.memory_service.add_message(ctx.turn.user_id, "assistant", reply)
            return ExecutionResult(
                capability=self.capability_name,
                messages=[reply],
                messages_recorded=True,
            )

        if ctx.onboarding_flow.is_active(ctx.turn.user_id):
            result = ctx.onboarding_flow.handle(ctx.turn.user_id, ctx.turn.message)
        else:
            result = {
                "completed": False,
                "reply": ctx.onboarding_flow.start(ctx.turn.user_id),
            }

        reply = result["reply"]
        ctx.memory_service.add_message(ctx.turn.user_id, "assistant", reply)

        extra_outputs = []
        if result.get("completed"):
            extra_outputs.append("--- Onboarding done. Student model saved. ---")

        return ExecutionResult(
            capability=self.capability_name,
            messages=[reply],
            extra_outputs=extra_outputs,
            messages_recorded=True,
            metadata={"completed": bool(result.get("completed"))},
        )

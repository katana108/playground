"""Executor for first-class document library operations."""

from __future__ import annotations

from .base import ExecutionResult


class DocumentOperationExecutor:
    """Run list/show/move/rename against the canonical document store."""

    def __init__(self, capability_name: str):
        self.capability_name = capability_name

    def execute(self, ctx, decision):
        service = getattr(ctx, "document_library_service", None)
        if not service:
            return ExecutionResult(
                capability=self.capability_name,
                messages=["I know this document capability exists, but the document-library service is not wired in this runtime yet."],
                messages_recorded=False,
            )

        target = dict(getattr(decision, "target", {}) or {})
        if self.capability_name == "list_documents":
            result = service.list_documents(
                user_id=ctx.turn.user_id,
                user_input=ctx.turn.message,
                current_focus=ctx.state.current_focus,
                explicit_topic=str(target.get("topic") or "").strip(),
                intent=str(getattr(decision, "intent", "") or ""),
            )
        elif self.capability_name == "show_document":
            result = service.show_document(
                user_id=ctx.turn.user_id,
                user_input=ctx.turn.message,
                current_focus=ctx.state.current_focus,
                target=target,
            )
        elif self.capability_name == "move_document":
            result = service.move_document(
                user_id=ctx.turn.user_id,
                user_input=ctx.turn.message,
                current_focus=ctx.state.current_focus,
                target=target,
            )
        elif self.capability_name == "rename_document":
            result = service.rename_document(
                user_id=ctx.turn.user_id,
                user_input=ctx.turn.message,
                current_focus=ctx.state.current_focus,
                target=target,
            )
        elif self.capability_name == "delete_topic":
            topic = str(target.get("topic") or "").strip()
            if not topic:
                # Fall back to extracting from raw message
                lowered = ctx.turn.message.lower()
                for marker in ("delete folder ", "delete topic ", "delete the folder ", "remove folder ", "remove topic "):
                    if marker in lowered:
                        topic = ctx.turn.message[lowered.index(marker) + len(marker):].strip(" .")
                        break
            result = service.delete_topic(
                user_id=ctx.turn.user_id,
                topic=topic,
            )
        else:
            result = {
                "status": "error",
                "message": f"Document capability `{self.capability_name}` is not implemented correctly.",
            }

        return ExecutionResult(
            capability=self.capability_name,
            messages=[result.get("message") or "I couldn't complete that document operation."],
            messages_recorded=False,
            state_delta=result.get("state_delta", {}) or {},
            metadata={"document_operation": result},
        )

"""Executor that confirms a batch of document operations before executing them."""

from __future__ import annotations

from .base import ExecutionResult


_OP_LABELS = {
    "move_document": lambda op: f"Move *{op.get('document_hint', '?')}* → *{op.get('destination_topic', '?')}*",
    "delete_topic": lambda op: f"Delete folder *{op.get('topic', '?')}*",
    "rename_document": lambda op: f"Rename *{op.get('document_hint', '?')}* → *{op.get('new_title', '?')}*",
}


class BatchConfirmExecutor:
    """Present a numbered confirmation list and park the ops for execution on 'yes'."""

    capability_name = "batch_confirm"

    def execute(self, ctx, decision):
        raw_ops = list(getattr(decision, "batch_operations", []) or [])
        ops = [op for op in raw_ops if str(op.get("capability", "")) in _OP_LABELS]
        if not ops:
            return ExecutionResult(
                capability=self.capability_name,
                messages=["I didn't catch distinct operations there — could you tell me what to do one step at a time?"],
                messages_recorded=False,
            )

        lines = ["Before I make any changes, let me read back what I understood:", ""]
        for i, op in enumerate(ops, 1):
            cap = str(op.get("capability", ""))
            label_fn = _OP_LABELS.get(cap)
            label = label_fn(op) if label_fn else f"{cap}: {op}"
            lines.append(f"{i}. {label}")
        lines += ["", "Is that all correct? Say *yes* to proceed or *cancel* to abort."]

        return ExecutionResult(
            capability=self.capability_name,
            messages=["\n".join(lines)],
            messages_recorded=False,
            state_delta={"pending_batch_ops": ops},
        )

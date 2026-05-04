"""Build the LLM-facing context view from larger stored history.

This is the first split between:
- what the system stores
- what the orchestrator chooses to send forward
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .models import CurrentFocus


@dataclass
class ContextView:
    """A smaller context package for one orchestrator/model call."""

    recent_messages: List[Dict[str, Any]] = field(default_factory=list)
    focus_summary: Dict[str, Any] = field(default_factory=dict)
    artifact_summaries: List[Dict[str, Any]] = field(default_factory=list)
    notes: Dict[str, Any] = field(default_factory=dict)


class ContextViewBuilder:
    """Create a focused view over a larger stored conversation history."""

    def __init__(self, max_recent_messages: int = 8):
        self.max_recent_messages = max_recent_messages

    def build(
        self,
        stored_messages: List[Dict[str, Any]],
        current_focus: CurrentFocus,
        artifact_summaries: List[Dict[str, Any]] | None = None,
        notes: Dict[str, Any] | None = None,
    ) -> ContextView:
        """Return the reduced context view for the next decision/respond step."""
        return ContextView(
            recent_messages=stored_messages[-self.max_recent_messages :],
            focus_summary={
                "kind": current_focus.kind.value if current_focus and current_focus.kind else "none",
                "artifact_id": current_focus.artifact_id,
                "topic": current_focus.topic,
                "lesson_id": current_focus.lesson_id,
                "curriculum_id": current_focus.curriculum_id,
                "updated_at": current_focus.updated_at,
            },
            artifact_summaries=artifact_summaries or [],
            notes=notes or {
                "stored_message_count": len(stored_messages),
                "context_message_count": min(len(stored_messages), self.max_recent_messages),
            },
        )

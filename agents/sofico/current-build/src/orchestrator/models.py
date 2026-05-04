"""Core data models for Sofi's orchestration layer.

These are software models, not AI models.
They define the shapes of the information the orchestrator reads and updates.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class FocusKind(str, Enum):
    """What Sofi is currently centered on."""

    NONE = "none"
    TOPIC = "topic"
    LESSON = "lesson"
    CURRICULUM = "curriculum"
    ARTIFACT = "artifact"
    REVIEW = "review"


class StudyArtifactType(str, Enum):
    """First-class learning objects Sofi can create or use."""

    UPLOADED_SOURCE = "uploaded_source"
    NOTES = "notes"
    QUESTION_SET = "question_set"
    COURSE_PLAN = "course_plan"
    LESSON_MATERIAL = "lesson_material"


@dataclass
class TurnContext:
    """Everything the orchestrator needs to understand one incoming turn."""

    user_id: str
    message: str
    normalized_message: str
    channel_id: str = ""
    message_ts: str = ""
    source: str = "slack"
    now_iso: str = ""
    attachments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CurrentFocus:
    """The thing Sofi believes the learner currently means by 'this' or 'it'."""

    kind: FocusKind = FocusKind.NONE
    artifact_id: str = ""
    topic: str = ""
    lesson_id: str = ""
    curriculum_id: str = ""
    source_message: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StudyArtifact:
    """A saved learning object that can be referenced later."""

    artifact_id: str
    artifact_type: StudyArtifactType
    title: str
    user_id: str
    topic: str = ""
    source_path: str = ""
    source_artifact_id: str = ""
    linked_plan_id: str = ""
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationState:
    """Short-lived conversation control state for the current learner."""

    active_mode: str = ""
    pending_action: str = ""
    recent_intent: str = ""
    temporary_overrides: Dict[str, Any] = field(default_factory=dict)
    current_focus: CurrentFocus = field(default_factory=CurrentFocus)
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratorResult:
    """Structured output of one orchestrator decision."""

    reply: str = ""
    action: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    should_clarify: bool = False
    clarification_question: str = ""
    updated_focus: Optional[CurrentFocus] = None
    updated_state: Optional[ConversationState] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

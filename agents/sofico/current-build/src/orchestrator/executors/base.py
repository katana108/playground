"""Base contracts for Sofico capability executors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from ..bootstrap_loader import OrchestratorBootstrapContext
from ..models import ConversationState, TurnContext
from ..reflection_engine import SessionReflectionInput
from ..turn_interpreter import TurnDecision


@dataclass
class ControllerHooks:
    """Narrow bridge from executors into controller-owned runtime helpers."""

    start_capture: Callable[[str, str, Optional[List[str]]], List[str]]
    execute_ingest: Callable[[str, Optional[str]], List[str]]
    handle_pending_ingest_confirmation: Callable[[str], List[str]]
    is_review_restart_request: Callable[[str], bool]
    should_escape_active_review: Callable[[str], bool]
    handle_active_review: Callable[[str], List[str]]
    start_review_session: Callable[[str], List[str]]
    should_escape_active_explanation: Callable[[str, Optional[Dict[str, Any]]], bool]
    handle_active_explanation: Callable[[str], List[str]]
    should_start_capture: Callable[[str, str], bool]
    should_auto_capture: Callable[[str, str], bool]
    infer_capture_intent: Callable[[str], str]
    try_start_explanation: Callable[[str, Optional[Dict[str, Any]]], List[str]]
    should_continue_from_focus: Callable[[str], bool]
    compose_teacher_reply: Callable[[str, str, OrchestratorBootstrapContext], str]
    show_artifacts: Callable[[str], List[str]]
    recall_recent_context: Callable[[], str]
    try_answer_from_matching_document: Callable[[str, str, Dict[str, Any], OrchestratorBootstrapContext], List[str]]
    refresh_focus_from_message: Callable[[str], None]


@dataclass
class ExecutorContext:
    """Everything one executor needs for one turn."""

    turn: TurnContext
    state: ConversationState
    bootstrap: OrchestratorBootstrapContext
    active_workflows: Dict[str, Any]
    data_service: Any
    memory_service: Any
    session_response_service: Any
    artifact_store: Any
    onboarding_flow: Any = None
    upload_handler: Any = None
    explanation_handler: Any = None
    study_handler: Any = None
    progress_handler: Any = None
    curriculum_handler: Any = None
    document_resolver_service: Any = None
    document_library_service: Any = None
    artifact_generation_service: Any = None
    research_service: Any = None
    topic_corpus_service: Any = None
    topic_synthesis_service: Any = None
    library_maintenance_service: Any = None
    learner_brief_service: Any = None
    hooks: Optional[ControllerHooks] = None


@dataclass
class ExecutionResult:
    """Structured result of one capability execution."""

    capability: str
    messages: List[str] = field(default_factory=list)
    extra_outputs: List[str] = field(default_factory=list)
    state_delta: Dict[str, Any] = field(default_factory=dict)
    writes: List[Dict[str, Any]] = field(default_factory=list)
    followup_action: str = ""
    reflection_input: Optional[SessionReflectionInput] = None
    messages_recorded: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapabilityExecutor(Protocol):
    """Shape-based executor interface."""

    capability_name: str

    def execute(self, ctx: ExecutorContext, decision: TurnDecision) -> ExecutionResult:
        """Run one capability turn."""
        ...

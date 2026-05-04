"""Primary control surface for Sofico's agent loop."""

import logging
import os
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from .bootstrap_loader import BootstrapLoader
from .capability_registry import CapabilityRegistry
from .context_engine import ActiveWorkflowContext, SoficoContextEngine
from .context_view import ContextViewBuilder
from .executors.artifact_executor import ArtifactExecutor
from .executors.base import ExecutionResult
from .executors.batch_confirm_executor import BatchConfirmExecutor
from .executors.conversation_executor import ConversationExecutor
from .executors.document_operation_executor import DocumentOperationExecutor
from .executors.ingest_executor import IngestExecutor
from .executors.library_maintenance_executor import LibraryMaintenanceExecutor
from .executors.onboarding_executor import OnboardingExecutor
from .executors.plan_executor import PlanExecutor
from .executors.progress_executor import ProgressExecutor
from .executors.recall_executor import RecallExecutor
from .executors.research_executor import ResearchExecutor
from .executors.review_executor import ReviewExecutor
from .executors.study_artifacts_executor import StudyArtifactsExecutor
from .executors.topic_synthesis_executor import TopicSynthesisExecutor
from .executors.upload_confirmation_executor import UploadConfirmationExecutor
from .models import ConversationState, CurrentFocus, OrchestratorResult, TurnContext
from .reflection_engine import ReflectionEngine
from .turn_interpreter import TurnDecision, TurnInterpreter


class SofiOrchestrator:
    """Coordinates intent, focus, capability selection, and response composition."""

    def __init__(
        self,
        profile_service: Any = None,
        memory_service: Any = None,
        data_service: Any = None,
        session_response_service: Any = None,
        bootstrap_loader: Optional[BootstrapLoader] = None,
        capability_registry: Optional[CapabilityRegistry] = None,
        learner_brief_service: Any = None,
        project_root: Optional[Path] = None,
    ):
        self.profile_service = profile_service
        self.memory_service = memory_service
        self.data_service = data_service
        self.session_response_service = session_response_service
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.bootstrap_loader = bootstrap_loader or BootstrapLoader(self.project_root)
        self.capability_registry = capability_registry or CapabilityRegistry()
        self.learner_brief_service = learner_brief_service
        self.context_view_builder = ContextViewBuilder()
        self.context_engine = SoficoContextEngine(
            bootstrap_loader=self.bootstrap_loader,
            capability_registry=self.capability_registry,
            data_service=self.data_service,
            memory_service=self.memory_service,
            learner_brief_service=self.learner_brief_service,
        )
        self.reflection_engine = ReflectionEngine()
        self.turn_interpreter = TurnInterpreter(self.session_response_service)
        self.turn_interpreter_mode = os.getenv("SOFICO_TURN_INTERPRETER_MODE", "shadow").lower()
        self.executors = self._build_executor_registry()

    def handle_turn(
        self,
        turn: TurnContext,
        conversation_state: Optional[ConversationState] = None,
    ) -> OrchestratorResult:
        """Return the current decision metadata without executing the capability."""
        state = conversation_state or ConversationState()
        focus = state.current_focus if state.current_focus else CurrentFocus()
        bootstrap = self.bootstrap_loader.load_context(turn.user_id)
        active_workflows = self._active_workflows_from_state(state)
        decision_bundle = self._decide_turn(turn, state, bootstrap, active_workflows)
        capability_name = decision_bundle["capability"]
        action = capability_name if capability_name != "converse" else None
        context_packet = decision_bundle["context_packet"]
        turn_decision = decision_bundle["turn_decision"]
        stored_messages = state.metadata.get("stored_messages", [])
        context_view = self.context_view_builder.build(
            stored_messages=stored_messages,
            current_focus=focus,
            artifact_summaries=state.metadata.get("artifact_summaries", []),
        )

        return OrchestratorResult(
            reply="",
            action=action,
            params={"capability": capability_name},
            should_clarify=False,
            clarification_question="",
            updated_focus=focus,
            updated_state=state,
            metadata={
                "status": "decision_loop_v1",
                "message": "Bootstrap context loads and a first capability decision loop is active.",
                "source": turn.source,
                "teacher_soul_loaded": bool(bootstrap.teacher_soul),
                "teacher_model_loaded": bool(bootstrap.teacher_model),
                "teacher_model_sections": sorted(bootstrap.teacher_model.keys()),
                "identity_loaded": bool(bootstrap.identity_text),
                "teaching_loaded": bool(bootstrap.teaching_text),
                "identity_fields": sorted(bootstrap.identity_defaults.keys()),
                "teaching_fields": sorted(bootstrap.teaching_defaults.keys()),
                "capability_names": sorted(self.capability_registry.summarize().keys()),
                "selected_capability": capability_name,
                "deterministic_capability": decision_bundle["fallback_capability"],
                "turn_interpreter_mode": self.turn_interpreter_mode,
                "turn_decision": self.turn_interpreter.to_dict(turn_decision) if turn_decision else {},
                "context_view_message_count": len(context_view.recent_messages),
                "context_packet": self.context_engine.to_dict(context_packet),
                "stored_message_count": context_view.notes.get("stored_message_count", 0),
                "student_model_sections": [
                    "identity",
                    "goals_and_constraints",
                    "stated_preferences_about_self",
                    "inferred_profile",
                    "progress_patterns",
                    "relationship_memory",
                ],
                "student_model_path": str(self.bootstrap_loader.student_model_store.get_path(turn.user_id)),
            },
        )

    def run_turn(
        self,
        turn: TurnContext,
        conversation_state: Optional[ConversationState],
        executor_context: Any,
    ) -> ExecutionResult:
        """Interpret, dispatch, and reflect for one learner turn."""
        state = conversation_state or ConversationState()
        bootstrap = getattr(executor_context, "bootstrap", None) or self.bootstrap_loader.load_context(turn.user_id)
        if getattr(executor_context, "bootstrap", None) is None:
            executor_context.bootstrap = bootstrap

        active_workflows = self._active_workflows_from_state(state)
        decision_bundle = self._decide_turn(turn, state, bootstrap, active_workflows)
        effective_capability = self._effective_capability(
            decision_bundle["turn_decision"],
            active_workflows,
            bootstrap.student_model,
        )
        executor = self.executors.get(effective_capability)
        if not executor:
            return ExecutionResult(
                capability=effective_capability,
                messages=[f"Capability `{effective_capability}` is registered but not executable in this runtime yet."],
                messages_recorded=False,
                metadata={
                    "selected_capability": effective_capability,
                    "turn_decision": self.turn_interpreter.to_dict(decision_bundle["turn_decision"]),
                },
            )

        executor_context.active_workflows = asdict(active_workflows)
        routed_decision = replace(decision_bundle["turn_decision"], capability=effective_capability)
        result = executor.execute(executor_context, routed_decision)

        applied_updates = self._apply_reflection(
            turn.user_id,
            bootstrap.student_model,
            result.reflection_input,
        )
        result.metadata.update(
            {
                "selected_capability": effective_capability,
                "fallback_capability": decision_bundle["fallback_capability"],
                "turn_decision": self.turn_interpreter.to_dict(routed_decision),
                "active_workflows": asdict(active_workflows),
                "reflection_updates_applied": len(applied_updates),
            }
        )
        return result

    def _active_workflows_from_state(self, state: ConversationState) -> ActiveWorkflowContext:
        """Read active workflow state supplied by the controller/transport layer."""
        raw = (state.metadata or {}).get("active_workflows", {}) or {}
        allowed = set(ActiveWorkflowContext.__dataclass_fields__.keys())
        filtered = {key: value for key, value in raw.items() if key in allowed}
        return ActiveWorkflowContext(**filtered)

    def summarize_capabilities(self) -> Dict[str, str]:
        """Describe the capability areas this orchestrator is expected to manage."""
        return self.capability_registry.summarize()

    def load_bootstrap_context(self, user_id: str) -> Dict[str, Any]:
        """Expose the loaded teacher + learner context for milestone testing."""
        context = self.bootstrap_loader.load_context(user_id)
        return {
            "teacher_soul": context.teacher_soul,
            "teacher_model": context.teacher_model,
            "identity_text": context.identity_text,
            "identity_defaults": context.identity_defaults,
            "teaching_text": context.teaching_text,
            "teaching_defaults": context.teaching_defaults,
            "student_model": context.student_model,
            "capabilities": self.capability_registry.list_capabilities(),
        }

    def _select_capability(self, turn: TurnContext, student_model: Any) -> str:
        """Choose a first-pass capability using simple intent heuristics."""
        text = turn.normalized_message.strip()
        raw_text = (turn.message or "").strip()
        if self._needs_onboarding(student_model):
            return "onboard_user"
        if not text:
            return "converse"
        if len(raw_text) >= 400 or ("\n" in raw_text and len(raw_text) >= 180):
            return "ingest_material"

        if self._matches_any(text, ["show progress", "my progress", "how am i doing", "what should i review"]):
            return "show_progress"
        if self._matches_any(text, ["find connections between all papers", "find connections across papers", "compare papers in", "compare all papers in", "what do these papers have in common", "synthesize this topic", "connect these papers"]):
            return "synthesize_topic"
        if self._matches_any(text, ["repair library", "repair my library", "reindex", "rebuild indexes", "dedupe", "clean duplicates", "repair artifacts"]):
            return "repair_library"
        if self._matches_any(text, ["move this paper", "move this document", "move paper", "move document", "put this paper in", "put this document in"]):
            return "move_document"
        if self._matches_any(text, ["delete folder", "delete topic", "delete this folder", "remove folder", "remove topic"]):
            return "delete_topic"
        if self._matches_any(text, ["rename this paper", "rename this document", "rename paper", "rename document", "call this paper", "name this paper"]):
            return "rename_document"
        if self._matches_any(text, ["show my papers", "list my papers", "list documents", "show papers", "papers are in", "documents are in", "show documents in", "papers in this folder", "documents in this topic"]):
            return "list_documents"
        if self._matches_any(text, ["show this paper", "show that paper", "show this document", "show that document", "paper profile", "document profile", "what is this paper", "what do you know about this paper"]):
            return "show_document"
        if self._matches_any(
            text,
            [
                "what were we doing",
                "where did we leave off",
                "what were we working on",
                "what was i studying",
                "what did we do last time",
                "continue where we left off",
                "remind me what we were doing",
            ],
        ):
            return "recall_context"
        if self._matches_any(
            text,
            [
                "quiz me",
                "test me",
                "review",
                "practice this topic",
                "give me recall questions",
                "recall questions",
                "ask me recall questions",
                "give me explain questions",
                "explain questions",
                "give me apply questions",
                "apply questions",
                "give me connect questions",
                "connect questions",
                "ask me questions",
            ],
        ):
            return "review"
        if self._matches_any(text, ["study plan", "curriculum", "plan my study", "plan two weeks", "make me a plan"]):
            return "plan_study"
        if self.is_material_inventory_request(text):
            return "show_artifacts"
        if self._matches_any(text, ["process this", "upload", "make notes from", "turn this into study materials", "create a study doc"]):
            return "ingest_material"
        if self._matches_any(text, ["make cards", "create notes", "generate review material", "prepare lesson materials"]):
            return "create_study_artifacts"
        if self._matches_any(text, ["latest", "find resources", "research", "look up", "search the web"]):
            return "research"
        if self._matches_any(text, ["explain", "teach me", "walk me through", "i don't understand", "help me understand"]):
            return "explain"
        return "converse"

    def _decide_turn(
        self,
        turn: TurnContext,
        state: ConversationState,
        bootstrap: Any,
        active_workflows: ActiveWorkflowContext,
    ) -> Dict[str, Any]:
        """Build the packet and select the first capability for this turn."""
        fallback_capability = self._select_capability(turn, bootstrap.student_model)
        capability_name = fallback_capability
        context_packet = self.context_engine.assemble(
            turn,
            state,
            bootstrap=bootstrap,
            active_workflows=active_workflows,
        )
        turn_decision = None
        if self.turn_interpreter_mode in {"shadow", "active"}:
            turn_decision = self.turn_interpreter.interpret(
                context_packet,
                fallback_capability=fallback_capability,
            )
            if self.turn_interpreter_mode == "active" and turn_decision.source == "llm":
                capability_name = turn_decision.capability

        logger.info(
            "TurnDecision: capability=%s intent=%s confidence=%.2f source=%s",
            turn_decision.capability if turn_decision else "none",
            turn_decision.intent if turn_decision else "none",
            turn_decision.confidence if turn_decision else 0.0,
            turn_decision.source if turn_decision else "none",
        )

        if turn_decision is None:
            turn_decision = TurnDecision(
                capability=fallback_capability,
                intent="fallback_no_interpreter",
                target={},
                continue_active_mode=True,
                needs_clarification=False,
                clarification_question="",
                confidence=0.0,
                debug_note="LLM interpreter disabled or not used for this turn.",
                source="fallback",
                error="Turn interpreter did not run.",
            )

        return {
            "fallback_capability": fallback_capability,
            "capability": capability_name,
            "turn_decision": turn_decision,
            "context_packet": context_packet,
        }

    def _effective_capability(
        self,
        decision: Any,
        active_workflows: ActiveWorkflowContext,
        student_model: Any,
    ) -> str:
        """Resolve workflow-first routing before executor dispatch."""
        requested = str(getattr(decision, "capability", "converse") or "converse")
        if active_workflows.pending_upload:
            return "upload_confirmation"
        if getattr(decision, "batch_operations", []):
            return "batch_confirm"
        if active_workflows.onboarding_active or self._needs_onboarding(student_model):
            return "onboard_user"
        if active_workflows.curriculum_active and decision.continue_active_mode and requested in {"plan_study", "converse"}:
            return "plan_study"
        if active_workflows.review_active and requested in {"show_artifacts", "recall_context", "ingest_material", "plan_study", "show_progress", "explain", "list_documents", "show_document", "move_document", "rename_document", "delete_topic", "batch_confirm", "synthesize_topic", "repair_library"}:
            return requested
        if active_workflows.review_active and decision.continue_active_mode and requested in {"review", "converse"}:
            return "review"
        if active_workflows.explanation_active and requested in {"review", "show_artifacts", "recall_context", "ingest_material", "plan_study", "show_progress", "list_documents", "show_document", "move_document", "rename_document", "delete_topic", "batch_confirm", "synthesize_topic", "repair_library"}:
            return requested
        if active_workflows.explanation_active and decision.continue_active_mode and requested in {"explain", "converse"}:
            return "explain"
        if str(getattr(decision, "intent", "")) == "answer_from_saved_document":
            return "explain"
        return requested

    def _build_executor_registry(self) -> Dict[str, Any]:
        """Return the executor instances used by the live agent loop."""
        conversation = ConversationExecutor()
        return {
            "onboard_user": OnboardingExecutor(),
            "upload_confirmation": UploadConfirmationExecutor(),
            "ingest_material": IngestExecutor(),
            "create_study_artifacts": StudyArtifactsExecutor(),
            "converse": conversation,
            "explain": conversation,
            "review": ReviewExecutor(),
            "show_artifacts": ArtifactExecutor(),
            "list_documents": DocumentOperationExecutor("list_documents"),
            "show_document": DocumentOperationExecutor("show_document"),
            "move_document": DocumentOperationExecutor("move_document"),
            "rename_document": DocumentOperationExecutor("rename_document"),
            "delete_topic": DocumentOperationExecutor("delete_topic"),
            "batch_confirm": BatchConfirmExecutor(),
            "synthesize_topic": TopicSynthesisExecutor(),
            "repair_library": LibraryMaintenanceExecutor(),
            "recall_context": RecallExecutor(),
            "plan_study": PlanExecutor(),
            "show_progress": ProgressExecutor(),
            "research": ResearchExecutor(),
        }

    def _apply_reflection(
        self,
        user_id: str,
        student_model: Any,
        reflection_input: Any,
    ) -> list[Any]:
        """Apply reflection-driven student-model updates after meaningful turns."""
        if not reflection_input:
            return []
        updates = self.reflection_engine.reflect(student_model, reflection_input)
        if not updates:
            return []
        updated_model = self.bootstrap_loader.student_model_store.apply_updates(
            user_id,
            updates,
            model=student_model,
        )
        self.bootstrap_loader.student_model_store.save(user_id, updated_model)
        return updates

    def _needs_onboarding(self, student_model: Any) -> bool:
        """Return True when the learner model lacks the minimum live-slice setup."""
        identity = getattr(student_model, "identity", {}) or {}
        goals = getattr(student_model, "goals_and_constraints", {}) or {}
        preferences = getattr(student_model, "stated_preferences_about_self", {}) or {}
        metadata = getattr(student_model, "metadata", {}) or {}

        if metadata.get("requires_v2_onboarding"):
            return True
        if not metadata.get("onboarding_completed_at"):
            return True

        name = str(identity.get("learner_name", "")).strip()
        goal_list = list(goals.get("study_goals", []) or [])
        subject_list = list(goals.get("preferred_subjects", []) or [])
        learning_preferences = list(preferences.get("learning_preferences", []) or [])
        return not (name and (goal_list or subject_list) and learning_preferences)

    def _matches_any(self, text: str, patterns: list[str]) -> bool:
        """Return True when any simple pattern appears in the turn."""
        return any(pattern in text for pattern in patterns)

    def is_material_inventory_request(self, text: str) -> bool:
        """Return True when the learner asks what saved materials exist."""
        direct_patterns = [
            "what materials",
            "which materials",
            "materials do i have",
            "available for explanation",
            "available for quiz",
            "what can you explain",
            "what can i quiz",
            "what files",
            "uploaded files",
            "what did you create",
            "what notes",
            "show notes",
            "show my notes",
            "what questions",
            "show questions",
            "what have we uploaded",
            "uploaded recently",
            "key concepts",
            "what did you save",
            "what topics",
            "list topics",
            "list materials",
        ]
        if self._matches_any(text, direct_patterns):
            return True

        material_terms = ("paper", "article", "document", "file", "upload", "uploaded", "material", "topic")
        inventory_terms = ("what about", "do i have", "you have", "have available", "saved", "uploaded")
        return any(term in text for term in material_terms) and any(term in text for term in inventory_terms)

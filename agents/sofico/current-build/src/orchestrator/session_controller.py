"""Reusable local session controller for Sofico conversation workflows.

This module owns conversation workflow state that should not live in a specific
transport like the terminal harness or Slack adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from handlers.curriculum_handler import CurriculumHandler
from handlers.explanation_handler import ExplanationHandler
from handlers.progress_handler import ProgressHandler
from handlers.study_handler import StudyHandler
from handlers.upload_handler import UploadHandler
from services.sm2_service import SM2Service
from services.conversation_memory_service import ConversationMemoryService
from services.artifact_view_service import ArtifactViewService
from services.document_library_service import DocumentLibraryService
from services.document_resolver_service import DocumentResolverService
from services.artifact_generation_service import ArtifactGenerationService
from services.library_maintenance_service import LibraryMaintenanceService
from services.local_file_service import LocalFileService
from services.profile_service import ProfileService
from services.research_service import ResearchService
from services.session_response_service import SessionResponseService
from services.learner_brief_service import LearnerBriefService
from services.topic_corpus_service import TopicCorpusService
from services.topic_synthesis_service import TopicSynthesisService

from .artifact_store import ArtifactStore
from .bootstrap_loader import OrchestratorBootstrapContext
from .executors.base import ControllerHooks, ExecutorContext
from .models import ConversationState, CurrentFocus, FocusKind, TurnContext
from .onboarding_flow import SoficoOnboardingFlow
from .orchestrator import SofiOrchestrator


@dataclass
class PasteCaptureState:
    """Temporary buffer for a multi-line pasted document."""

    intent: str = "ingest_material"
    lines: List[str] = field(default_factory=list)
    source_request: str = ""


class SessionController:
    """Own one learner session across onboarding, ingest, focus, and explanation."""

    def __init__(
        self,
        project_root: Path,
        user_id: str,
        data_service: Optional[Any] = None,
        memory_service: Optional[ConversationMemoryService] = None,
        profile_service: Optional[ProfileService] = None,
        session_response_service: Optional[SessionResponseService] = None,
        artifact_store: Optional[ArtifactStore] = None,
        orchestrator: Optional[SofiOrchestrator] = None,
        onboarding_flow: Optional[SoficoOnboardingFlow] = None,
        upload_handler: Optional[UploadHandler] = None,
        explanation_handler: Optional[ExplanationHandler] = None,
        study_handler: Optional[StudyHandler] = None,
        progress_handler: Optional[ProgressHandler] = None,
        curriculum_handler: Optional[CurriculumHandler] = None,
        source: str = "cli",
        include_debug: bool = True,
    ):
        self.project_root = Path(project_root)
        self.user_id = user_id
        self.source = source
        self.include_debug = include_debug

        self.data_service = data_service or LocalFileService()
        self.memory_service = memory_service or ConversationMemoryService(self.data_service)
        self.profile_service = profile_service or ProfileService(data_service=self.data_service)
        self.session_response_service = session_response_service or SessionResponseService(
            data_service=self.data_service,
            memory_service=self.memory_service,
        )
        self.artifact_store = artifact_store or ArtifactStore(self.project_root)
        self.learner_brief_service = LearnerBriefService(
            data_service=self.data_service,
            profile_service=self.profile_service,
        )
        self.orchestrator = orchestrator or SofiOrchestrator(
            data_service=self.data_service,
            memory_service=self.memory_service,
            session_response_service=self.session_response_service,
            learner_brief_service=self.learner_brief_service,
            project_root=self.project_root,
        )
        if not getattr(self.orchestrator, "learner_brief_service", None):
            self.orchestrator.learner_brief_service = self.learner_brief_service
        if getattr(self.orchestrator, "context_engine", None):
            self.orchestrator.context_engine.learner_brief_service = self.learner_brief_service
        self.onboarding_flow = onboarding_flow or SoficoOnboardingFlow(
            student_model_store=self.orchestrator.bootstrap_loader.student_model_store,
            profile_service=self.profile_service,
        )
        self.upload_handler = upload_handler or UploadHandler(
            gitlab_service=self.data_service,
            slack_app=None,
            session_response_service=self.session_response_service,
            artifact_store=self.artifact_store,
        )
        self.explanation_handler = explanation_handler or ExplanationHandler(
            data_service=self.data_service,
            session_response_service=self.session_response_service,
            profile_service=self.profile_service,
        )
        self.study_handler = study_handler or StudyHandler(
            gitlab_service=self.data_service,
            sm2_service=SM2Service(),
            session_response_service=self.session_response_service,
        )
        self.progress_handler = progress_handler or ProgressHandler(
            gitlab_service=self.data_service,
        )
        self.curriculum_handler = curriculum_handler or CurriculumHandler(
            data_service=self.data_service,
            session_response_service=self.session_response_service,
            profile_service=self.profile_service,
            artifact_store=self.artifact_store,
        )
        self.document_resolver = DocumentResolverService(self.artifact_store)
        self.artifact_view_service = ArtifactViewService(
            data_service=self.data_service,
            artifact_store=self.artifact_store,
            document_resolver=self.document_resolver,
        )
        self.document_library_service = DocumentLibraryService(
            data_service=self.data_service,
            artifact_store=self.artifact_store,
            document_resolver=self.document_resolver,
        )
        self.artifact_generation_service = ArtifactGenerationService(
            data_service=self.data_service,
            artifact_store=self.artifact_store,
        )
        self.topic_corpus_service = TopicCorpusService(
            data_service=self.data_service,
        )
        self.topic_synthesis_service = TopicSynthesisService(
            session_response_service=self.session_response_service,
        )
        self.library_maintenance_service = LibraryMaintenanceService(
            data_service=self.data_service,
            artifact_store=self.artifact_store,
            topic_corpus_service=self.topic_corpus_service,
        )
        self.research_service = ResearchService(
            model=self.session_response_service.model,
        )

        self.state = self._load_conversation_state()
        self.capture_state: Optional[PasteCaptureState] = None

    def startup_messages(self) -> List[str]:
        """Return the initial greeting for this learner session."""
        model = self.orchestrator.bootstrap_loader.load_student_model(self.user_id)
        if self.onboarding_flow.needs_onboarding(model):
            return [f"Sofico: {self.onboarding_flow.start(self.user_id)}"]

        name = (
            (model.identity or {}).get("preferred_form_of_address")
            or (model.identity or {}).get("learner_name")
            or "there"
        )
        return [
            f"Sofico: Welcome back, {name}. You can ask me to explain something, "
            "paste text with /paste, or say what you want to learn."
        ]

    def prompt(self) -> str:
        """Prompt depends on whether we are collecting a multi-line paste buffer."""
        return "" if self.capture_state else "You: "

    def start_manual_paste(self) -> List[str]:
        """Manually enter buffered paste mode from the transport layer."""
        return self._start_capture(
            intent=self._infer_capture_intent(""),
            source_request="",
        )

    def register_external_ingest_result(
        self,
        ingest_result: Optional[dict],
        source_message: str = "",
        requested_followup: Optional[str] = None,
    ) -> List[str]:
        """Record an ingest result produced by a transport-specific file upload.

        Slack file extraction is transport-specific, but the resulting document
        state should still flow through the shared session controller.
        """
        self.state.metadata["last_ingest_result"] = ingest_result
        self._update_focus_from_ingest(ingest_result, source_message=source_message)
        self._remember_ingest_followup(ingest_result, requested_followup=requested_followup)
        return self._maybe_continue_after_ingest(ingest_result, requested_followup=requested_followup)

    def handle_input(self, raw_input_text: str) -> List[str]:
        """Process one user input and return transport-ready output lines."""
        user_input = raw_input_text.strip()

        if self.capture_state:
            if user_input.lower() in {"end", "done", "finish", "process now"}:
                return self._finalize_capture()
            if user_input.lower() in {"/cancel", "cancel"}:
                self.capture_state = None
                return ["Sofico: Okay. I cleared the current paste buffer."]
            self.capture_state.lines.append(raw_input_text)
            return []

        # Intercept before TurnInterpreter when a batch confirmation is pending.
        if self.state.metadata.get("pending_batch_ops"):
            lowered = user_input.lower().strip()
            if self._is_batch_confirmation(lowered):
                self.memory_service.add_message(self.user_id, "user", user_input)
                results = self._execute_pending_batch_ops()
                self.state.metadata["stored_messages"] = self.memory_service.get_history(self.user_id)
                self._persist_conversation_state()
                return results
            if self._is_batch_cancellation(lowered):
                self.memory_service.add_message(self.user_id, "user", user_input)
                self.state.metadata.pop("pending_batch_ops", None)
                self._persist_conversation_state()
                msg = "Got it — I've cancelled those pending changes."
                self.memory_service.add_message(self.user_id, "assistant", msg)
                return [f"Sofico: {msg}"]

        self.memory_service.check_timeout(self.user_id)
        self.memory_service.add_message(self.user_id, "user", user_input)

        turn = TurnContext(
            user_id=self.user_id,
            message=user_input,
            normalized_message=user_input.lower(),
            source=self.source,
        )
        self.state.metadata["stored_messages"] = self.memory_service.get_history(self.user_id)
        self.state.metadata["active_workflows"] = self._active_workflow_context()
        bootstrap = self.orchestrator.bootstrap_loader.load_context(self.user_id)
        if not self.onboarding_flow.needs_onboarding(bootstrap.student_model):
            self.onboarding_flow.clear(self.user_id)

        executor_context = self._build_executor_context(turn, bootstrap)
        execution = self.orchestrator.run_turn(turn, self.state, executor_context)
        self._apply_execution_state(execution.state_delta)

        if not execution.messages_recorded:
            for message in execution.messages:
                clean = self._strip_transport_prefix(message)
                if clean:
                    self.memory_service.add_message(self.user_id, "assistant", clean)

        self.state.metadata["stored_messages"] = self.memory_service.get_history(self.user_id)
        self.state.metadata["active_workflows"] = self._active_workflow_context()
        self._persist_conversation_state()

        outputs = [f"[capability] {execution.capability}"] if self.include_debug else []
        outputs.extend(self._render_executor_messages(execution.messages))
        outputs.extend(execution.extra_outputs)
        return outputs

    def _build_executor_context(
        self,
        turn: TurnContext,
        bootstrap: OrchestratorBootstrapContext,
    ) -> ExecutorContext:
        """Assemble the per-turn executor context for the agent loop."""
        return ExecutorContext(
            turn=turn,
            state=self.state,
            bootstrap=bootstrap,
            active_workflows=self._active_workflow_context(),
            data_service=self.data_service,
            memory_service=self.memory_service,
            session_response_service=self.session_response_service,
            artifact_store=self.artifact_store,
            onboarding_flow=self.onboarding_flow,
            upload_handler=self.upload_handler,
            explanation_handler=self.explanation_handler,
            study_handler=self.study_handler,
            progress_handler=self.progress_handler,
            curriculum_handler=self.curriculum_handler,
            document_resolver_service=self.document_resolver,
            document_library_service=self.document_library_service,
            artifact_generation_service=self.artifact_generation_service,
            research_service=self.research_service,
            topic_corpus_service=self.topic_corpus_service,
            topic_synthesis_service=self.topic_synthesis_service,
            library_maintenance_service=self.library_maintenance_service,
            learner_brief_service=self.learner_brief_service,
            hooks=self._build_controller_hooks(),
        )

    def _apply_execution_state(self, state_delta: Dict[str, Any]):
        """Apply executor-supplied focus/activity updates in one standard place."""
        if not state_delta:
            return

        if state_delta.get("clear_learning_modes"):
            self._clear_active_learning_modes()

        focus_payload = state_delta.get("focus")
        if isinstance(focus_payload, dict) and focus_payload:
            self.state.current_focus = self._focus_from_dict(focus_payload)

        activity_payload = state_delta.get("activity")
        if isinstance(activity_payload, dict) and activity_payload:
            self._set_activity_metadata(
                kind=str(activity_payload.get("kind") or "").strip(),
                summary=str(activity_payload.get("summary") or "").strip(),
                topic=str(activity_payload.get("topic") or "").strip(),
            )

        # BatchConfirmExecutor parks operations here; session controller executes on confirmation.
        pending_ops = state_delta.get("pending_batch_ops")
        if pending_ops is not None:
            self.state.metadata["pending_batch_ops"] = list(pending_ops)
            self._persist_conversation_state()

    def _current_learner_brief(
        self,
        bootstrap: Optional[OrchestratorBootstrapContext] = None,
    ) -> Dict[str, Any]:
        """Build the shared learner brief for this user."""
        bootstrap = bootstrap or self.orchestrator.bootstrap_loader.load_context(self.user_id)
        return self.learner_brief_service.build(
            self.user_id,
            student_model=bootstrap.student_model,
        )

    def _build_controller_hooks(self) -> ControllerHooks:
        """Expose controller helpers without leaking transport formatting."""
        return ControllerHooks(
            start_capture=lambda intent, source_request, initial_lines=None: self._strip_transport_prefixes(
                self._start_capture(intent, source_request, initial_lines)
            ),
            execute_ingest=lambda user_input, requested_followup=None: self._strip_transport_prefixes(
                self._execute_ingest(user_input, requested_followup=requested_followup)
            ),
            handle_pending_ingest_confirmation=lambda user_input: self._strip_transport_prefixes(
                self._handle_pending_ingest_confirmation(user_input)
            ),
            is_review_restart_request=self._is_review_restart_request,
            should_escape_active_review=self._should_escape_active_review,
            handle_active_review=lambda user_input: self._strip_transport_prefixes(
                self._handle_active_review(user_input)
            ),
            start_review_session=lambda user_input: self._strip_transport_prefixes(
                self._start_review_session(user_input)
            ),
            should_escape_active_explanation=self._should_escape_active_explanation,
            handle_active_explanation=lambda user_input: self._strip_transport_prefixes(
                self._handle_active_explanation(user_input)
            ),
            should_start_capture=self._should_start_capture,
            should_auto_capture=self._should_auto_capture,
            infer_capture_intent=self._infer_capture_intent,
            try_start_explanation=lambda user_input, target=None: self._strip_transport_prefixes(
                self._try_start_explanation(user_input, target=target)
            ),
            should_continue_from_focus=self._should_continue_from_focus,
            compose_teacher_reply=self._compose_teacher_reply,
            show_artifacts=lambda user_input: self._strip_transport_prefixes(
                self._show_artifacts(user_input)
            ),
            recall_recent_context=lambda intent="": self._strip_transport_prefix(
                self._recall_recent_context(intent=intent)
            ),
            try_answer_from_matching_document=lambda user_input, capability, result, bootstrap: self._strip_transport_prefixes(
                self._try_answer_from_matching_document(
                    user_input,
                    capability,
                    result,
                    bootstrap=bootstrap,
                )
            ),
            refresh_focus_from_message=self._refresh_focus_from_message,
        )

    def _render_executor_messages(self, messages: List[str]) -> List[str]:
        """Render raw executor messages into transport-ready output lines."""
        return [self._render_assistant_message(message) for message in messages if message]

    def _render_assistant_message(self, message: str) -> str:
        """Apply the local harness label only when needed."""
        if not message:
            return ""
        if message.startswith("Sofico: ") or message.startswith("---"):
            return message
        return f"Sofico: {message}"

    def _strip_transport_prefixes(self, messages: List[str]) -> List[str]:
        """Remove local harness prefixes from helper outputs."""
        return [self._strip_transport_prefix(message) for message in messages if message]

    def _strip_transport_prefix(self, message: str) -> str:
        """Normalize one helper output into raw assistant text."""
        if not message:
            return ""
        return message[len("Sofico: "):] if message.startswith("Sofico: ") else message

    def _is_review_restart_request(self, user_input: str) -> bool:
        """Return True when the learner asks for a new review session, not an answer."""
        lowered = user_input.lower()
        restart_signals = (
            "quiz me",
            "test me",
            "give me",
            "ask me",
            "ask questions",
            "now ask questions",
            "now questions",
            "recall questions",
            "explain questions",
            "apply questions",
            "connect questions",
        )
        return any(signal in lowered for signal in restart_signals)

    def _active_workflow_context(self) -> Dict[str, Any]:
        """Expose controller-owned workflow state to the context engine."""
        curriculum_active = self.curriculum_handler.is_active(self.user_id)
        curriculum = self.curriculum_handler.active_curricula.get(self.user_id, {})
        explanation = self.explanation_handler.active_explanations.get(self.user_id, {})
        review = self.study_handler.active_sessions.get(self.user_id, {})
        review_questions = review.get("questions", []) if isinstance(review, dict) else []
        review_index = int(review.get("current_index", 0) or 0) if isinstance(review, dict) else 0
        review_topic = ""
        if review_questions and review_index < len(review_questions):
            review_topic = review_questions[review_index].get("topic", "")

        return {
            "onboarding_active": self.onboarding_flow.is_active(self.user_id),
            "pending_upload": self.upload_handler.has_pending(self.user_id),
            "curriculum_active": curriculum_active,
            "curriculum_subject": curriculum.get("subject", ""),
            "explanation_active": self.explanation_handler.is_active(self.user_id),
            "explanation_topic": explanation.get("topic", ""),
            "review_active": self.user_id in self.study_handler.active_sessions,
            "review_topic": review_topic,
            "review_scope_type": review.get("scope_type", "") if isinstance(review, dict) else "",
            "review_scope_label": review.get("scope_label", "") if isinstance(review, dict) else "",
            "review_question_index": review_index,
            "review_question_count": len(review_questions),
            "capture_active": bool(self.capture_state),
        }

    def _clear_active_learning_modes(self):
        """Clear stale quiz/explanation modes when new material becomes the focus."""
        if self.explanation_handler.is_active(self.user_id):
            self.explanation_handler.cancel(self.user_id)
        if self.user_id in self.study_handler.active_sessions:
            self.study_handler.cancel_session(self.user_id)

    def _should_escape_active_explanation(self, user_input: str, target: dict = None) -> bool:
        """Escape an active explanation session when the user clearly wants a different topic or document.

        Uses the LLM's resolved target as the primary signal.  Keyword-based
        escape phrases are a secondary fallback for cases where the interpreter
        did not fire or returned low confidence.
        """
        active = self.explanation_handler.active_explanations.get(self.user_id, {})
        if not active:
            return False
        active_topic = (active.get("topic") or "").strip()
        active_doc_name = str(active.get("doc_name", "") or "").strip()

        # Primary: use the LLM-resolved target to detect a topic/document switch.
        if target:
            target_topic = str(target.get("topic") or target.get("document_hint") or "").strip()
            target_doc = str(target.get("artifact_hint") or "").strip()
            if target_topic and target_topic != active_topic:
                self.explanation_handler.cancel(self.user_id)
                return True
            if target_doc and active_doc_name and target_doc != active_doc_name:
                self.explanation_handler.cancel(self.user_id)
                return True

        # Secondary: artifact-based check for document-scoped sessions.
        resolved_artifact = self._resolve_explanation_artifact(user_input)
        if resolved_artifact:
            resolved_doc_name = self._artifact_doc_name(resolved_artifact)
            if resolved_doc_name and resolved_doc_name != active_doc_name:
                self.explanation_handler.cancel(self.user_id)
                return True

        # Stay in session when the active topic matches current focus.
        focused_topic = self._focused_topic()
        if active_topic == focused_topic and active.get("scope_type", "topic") != "document":
            return False

        # Tertiary: explicit user correction phrases.
        lowered = user_input.lower()
        escape_signals = (
            "wrong paper",
            "wrong document",
            "article i just gave",
            "paper i just gave",
            "document i just gave",
            "just gave you",
            "just uploaded",
        )
        if any(signal in lowered for signal in escape_signals):
            self.explanation_handler.cancel(self.user_id)
            return True
        return False

    def _should_escape_active_review(self, user_input: str) -> bool:
        """Let explicit current-material requests escape a stale quiz session."""
        if not self._focused_topic():
            return False
        lowered = user_input.lower()
        escape_signals = (
            "only this paper",
            "only about this paper",
            "just this paper",
            "just this document",
            "not all topics",
            "not this topic",
            "now ask questions",
            "ask questions about this",
            "questions for this paper",
            "quiz me on this",
            "first explain",
            "explain it",
            "explain this",
            "from the article",
            "from this article",
            "article i just gave",
            "not the old",
            "just gave you",
            "just uploaded",
        )
        if any(signal in lowered for signal in escape_signals):
            self.study_handler.cancel_session(self.user_id)
            return True
        return False

    def _handle_active_review(self, user_input: str) -> List[str]:
        """Continue an existing quiz session using the proven StudyHandler."""
        raw_outputs: List[str] = []
        self.study_handler.handle(
            {"user": self.user_id, "text": user_input},
            self._collector(raw_outputs),
            learner_brief=self._current_learner_brief(),
        )
        rendered = [f"Sofico: {message}" for message in raw_outputs]
        for message in raw_outputs:
            self.memory_service.add_message(self.user_id, "assistant", message)
        if self.user_id not in self.study_handler.active_sessions:
            self.memory_service.end_session(self.user_id)
        return rendered

    def _start_review_session(self, user_input: str) -> List[str]:
        """Start a quiz, preferring a focused/matched document when the learner asks for one paper."""
        artifact = self._resolve_review_artifact(user_input)
        if artifact:
            questions = self._load_artifact_questions(artifact)
            if questions:
                raw_outputs: List[str] = []
                title = self._artifact_title(artifact)
                topic = (artifact.topic or "").strip()
                doc_name = self._artifact_doc_name(artifact)
                self.study_handler.start_document_session(
                    self.user_id,
                    artifact_title=title,
                    topic=topic,
                    doc_name=doc_name,
                    questions=questions,
                    say=self._collector(raw_outputs),
                    learner_brief=self._current_learner_brief(),
                )
                rendered = [f"Sofico: {message}" for message in raw_outputs]
                for message in raw_outputs:
                    self.memory_service.add_message(self.user_id, "assistant", message)
                self._set_focus_artifact(artifact, user_input)
                self._remember_activity(
                    kind="review",
                    summary=f"Started a quiz on {title}.",
                    topic=topic,
                )
                if self.user_id not in self.study_handler.active_sessions:
                    self.memory_service.end_session(self.user_id)
                return rendered

        topic = self._resolve_review_topic(user_input)
        if topic:
            category_filter = self.study_handler._extract_category_filter(user_input)
            corpus_questions = self.topic_corpus_service.review_questions(
                self.user_id,
                topic,
                due_only=True,
                category_filter=category_filter,
            )
            corpus = self.topic_corpus_service.load_corpus(self.user_id, topic)
            if corpus_questions and corpus.document_count:
                raw_outputs: List[str] = []
                self.study_handler.start_topic_corpus_session(
                    self.user_id,
                    topic=topic,
                    questions=corpus_questions,
                    document_titles=self.topic_corpus_service.topic_titles(corpus),
                    say=self._collector(raw_outputs),
                    learner_brief=self._current_learner_brief(),
                )
                rendered = [f"Sofico: {message}" for message in raw_outputs]
                for message in raw_outputs:
                    self.memory_service.add_message(self.user_id, "assistant", message)
                self._set_focus_topic(topic, source_message=user_input)
                self._remember_activity(
                    kind="review",
                    summary=f"Started a topic-corpus quiz on {topic}.",
                    topic=topic,
                )
                if self.user_id not in self.study_handler.active_sessions:
                    self.memory_service.end_session(self.user_id)
                return rendered

        event_text = f"quiz me on {topic}" if topic else user_input

        raw_outputs: List[str] = []
        self.study_handler.handle(
            {"user": self.user_id, "text": event_text},
            self._collector(raw_outputs),
            learner_brief=self._current_learner_brief(),
        )
        rendered = [f"Sofico: {message}" for message in raw_outputs]
        for message in raw_outputs:
            self.memory_service.add_message(self.user_id, "assistant", message)
        if topic:
            self._set_focus_topic(topic, source_message=user_input)
            self._remember_activity(
                kind="review",
                summary=f"Started a quiz on {topic}.",
                topic=topic,
            )
        if self.user_id not in self.study_handler.active_sessions:
            self.memory_service.end_session(self.user_id)
        return rendered

    def _resolve_review_artifact(self, user_input: str) -> Optional[Any]:
        """Resolve a document-scoped quiz target from the learner turn or current focus."""
        return self.document_resolver.resolve_for_review(
            self.user_id,
            user_input,
            self.state.current_focus,
        )

    def _show_artifacts(self, user_input: str) -> List[str]:
        """Describe saved notes/questions for the current or requested topic."""
        explicit_topic = self._explicit_topic_reference(user_input)
        outcome = self.artifact_view_service.show_artifacts(
            user_id=self.user_id,
            user_input=user_input,
            current_focus=self.state.current_focus,
            explicit_topic=explicit_topic,
            resolved_topic=self._resolve_artifact_topic(user_input),
            references_current_material=self._references_current_material(user_input.lower()),
            inventory_request=self.orchestrator.is_material_inventory_request(user_input.lower()),
        )

        if outcome.clear_learning_modes:
            self._clear_active_learning_modes()
        if outcome.focus_artifact:
            self._set_focus_artifact(outcome.focus_artifact, user_input)
        elif outcome.focus_topic:
            self._set_focus_topic(outcome.focus_topic, source_message=user_input)
        if outcome.activity_kind:
            self._remember_activity(
                kind=outcome.activity_kind,
                summary=outcome.activity_summary,
                topic=outcome.activity_topic,
            )
        return [outcome.message]

    def _explicit_topic_reference(self, user_input: str) -> Optional[str]:
        """Return a topic only when the learner explicitly names the topic folder."""
        return self.document_resolver.extract_topic_reference(
            user_input,
            self.data_service.get_available_topics(self.user_id),
        )

    def _focused_artifact(self) -> Optional[Any]:
        """Return the currently focused artifact, if it still exists."""
        return self.document_resolver.focused_artifact(self.user_id, self.state.current_focus)

    def _try_answer_from_matching_document(
        self,
        user_input: str,
        capability: str,
        result: Any = None,
        bootstrap: Optional[OrchestratorBootstrapContext] = None,
    ) -> List[str]:
        """Answer a content question from a specifically matched saved document."""
        if not self._should_answer_from_document(user_input, capability):
            return []

        query_text = user_input
        if isinstance(result, dict):
            turn_decision = result
        else:
            turn_decision = (getattr(result, "metadata", {}) or {}).get("turn_decision", {}) or {}
        target = turn_decision.get("target", {}) if isinstance(turn_decision, dict) else {}
        if isinstance(target, dict):
            target_hint = " ".join(str(value or "") for value in target.values())
            query_text = f"{user_input} {target_hint}".strip()

        artifact = self.document_resolver.select_document_artifact(
            self.document_resolver.matching_artifacts(self.user_id, query_text)
        )
        if not artifact:
            return []

        notes = self._load_artifact_notes(artifact)
        if not notes:
            return []

        self._clear_active_learning_modes()
        self._set_focus_artifact(artifact, user_input)
        reply = self._compose_document_answer(user_input, artifact, notes, bootstrap=bootstrap)
        self.explanation_handler.activate_document_session(
            self.user_id,
            artifact_title=self._artifact_title(artifact),
            topic=(artifact.topic or "").strip(),
            doc_name=self._artifact_doc_name(artifact),
            notes_only=notes,
            learner_brief=self._current_learner_brief(bootstrap),
            history=[
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": reply},
            ],
        )
        self.memory_service.add_message(self.user_id, "assistant", reply)
        return [f"Sofico: {reply}"]

    def _should_answer_from_document(self, user_input: str, capability: str) -> bool:
        """Return True when a turn asks for content, not a material inventory."""
        lowered = user_input.lower()
        answer_signals = (
            "according to",
            "look into",
            "look at",
            "what does",
            "what do they say",
            "what he says",
            "what she says",
            "what it says",
            "what does it say",
            "see what",
            "from the paper",
            "from this paper",
            "from the article",
            "from this article",
            "in the paper",
            "in this paper",
            "in the article",
            "in this article",
            "specifically asked",
            "explain how",
            "explain why",
        )
        wants_answer = self._looks_like_learning_question(user_input) or any(
            signal in lowered for signal in answer_signals
        )
        if not wants_answer:
            return False
        if capability not in {"converse", "explain", "show_artifacts"}:
            return False
        if self.orchestrator.is_material_inventory_request(lowered) and not any(
            signal in lowered for signal in answer_signals
        ):
            return False
        return True

    def _select_document_artifact(self, artifacts: List[Any]) -> Optional[Any]:
        """Pick the best document-like artifact for answering."""
        return self.document_resolver.select_document_artifact(artifacts)

    def _resolve_artifact_doc_id(self, artifact: Any) -> str:
        """Return doc_id for an artifact, with fallback for legacy artifacts that lack it in metadata.

        Resolution order:
        1. artifact.metadata["doc_id"]  — fast, present for artifacts created after doc_id was added
        2. companion artifact with same source_path — handles same-batch saves where no artifact got doc_id
        3. manifest scan by legacy_topic_document_path — last resort for truly old artifacts
        """
        doc_id = str((artifact.metadata or {}).get("doc_id", "") or "").strip()
        if doc_id:
            return doc_id

        source_path = str(artifact.source_path or "").strip()
        if source_path:
            for companion in self.artifact_store.list_artifacts(self.user_id):
                if companion.artifact_id == artifact.artifact_id:
                    continue
                if str(companion.source_path or "").strip() != source_path:
                    continue
                candidate = str((companion.metadata or {}).get("doc_id", "") or "").strip()
                if candidate:
                    return candidate

        doc_name = self._artifact_doc_name(artifact)
        if doc_name and hasattr(self.data_service, "list_document_manifests"):
            # artifact.source_path: "{topic}/{doc_name}.md"
            # manifest legacy path: "topics/{topic}/{doc_name}.md"
            source_path_norm = str(artifact.source_path or "").strip()
            for manifest in self.data_service.list_document_manifests(self.user_id):
                storage = manifest.get("storage") or {}
                manifest_legacy = str(storage.get("legacy_topic_document_path", "") or "").strip()
                manifest_slug = str(manifest.get("slug", "") or "").strip()
                legacy_doc_name = Path(manifest_legacy).stem if manifest_legacy else ""
                matches = (
                    (source_path_norm and manifest_legacy == f"topics/{source_path_norm}")
                    or (legacy_doc_name and legacy_doc_name.lower() == doc_name.lower())
                    or (manifest_slug and manifest_slug.lower() == doc_name.lower())
                )
                if matches:
                    found = str(manifest.get("doc_id", "") or "").strip()
                    if found:
                        return found
        return ""

    def _load_artifact_notes(self, artifact: Any) -> str:
        """Load notes for the exact document represented by an artifact."""
        doc_id = self._resolve_artifact_doc_id(artifact)
        if doc_id and hasattr(self.data_service, "get_document_notes"):
            notes = self.data_service.get_document_notes(self.user_id, doc_id) or ""
            if notes:
                return notes

        topic = (artifact.topic or "").strip()
        doc_name = self._artifact_doc_name(artifact)
        if not topic or not doc_name:
            return ""
        if hasattr(self.data_service, "get_study_document_notes"):
            notes = self.data_service.get_study_document_notes(self.user_id, topic, doc_name)
            if notes:
                return notes

        topic_notes = self.data_service.get_topic_notes(self.user_id, topic)
        if not topic_notes:
            return ""
        marker = f"### {Path(doc_name).stem}"
        if marker not in topic_notes:
            return topic_notes
        section = topic_notes.split(marker, 1)[1].strip()
        next_section = section.find("\n### ")
        return section[:next_section].strip() if next_section != -1 else section

    def _load_artifact_questions(self, artifact: Any) -> List[Dict[str, Any]]:
        """Load indexed questions for one exact document represented by an artifact."""
        doc_id = self._resolve_artifact_doc_id(artifact)
        if doc_id and hasattr(self.data_service, "get_document_questions"):
            questions = self.data_service.get_document_questions(self.user_id, doc_id) or []
            if questions:
                return questions

        topic = (artifact.topic or "").strip()
        doc_name = self._artifact_doc_name(artifact)
        if not topic or not doc_name:
            return []

        index_data = self.data_service.get_topic_index(self.user_id, topic)
        if not isinstance(index_data, dict):
            return []

        doc_prefixes = {
            f"{doc_name}.md#",
            f"{Path(doc_name).stem}.md#",
        }
        questions = []
        for question in index_data.get("questions", []):
            question_id = str(question.get("id", "") or "")
            if any(question_id.startswith(prefix) for prefix in doc_prefixes):
                questions.append(question)
        return questions

    def _artifact_doc_name(self, artifact: Any) -> str:
        """Resolve the study document filename/stem from artifact metadata."""
        return self.document_resolver.artifact_doc_name(artifact)

    def _artifact_title(self, artifact: Any) -> str:
        """Return a readable title for one artifact."""
        return self.document_resolver.artifact_title(artifact)

    def _set_focus_artifact(self, artifact: Any, source_message: str):
        """Set current focus to the exact document used for an answer."""
        topic = (artifact.topic or "").strip()
        if not topic:
            return
        doc_name = self._artifact_doc_name(artifact)
        self.state.current_focus = CurrentFocus(
            kind=FocusKind.ARTIFACT,
            artifact_id=artifact.artifact_id,
            topic=topic,
            source_message=source_message[:200],
            updated_at=self._now_iso(),
            metadata={
                "document_title": self._artifact_title(artifact),
                "doc_name": doc_name,
                "source_path": artifact.source_path or f"{topic}/{doc_name}.md",
                "matched_document_answer": True,
            },
        )
        self._remember_activity(
            kind="document_answer",
            summary=f"Answered from {self._artifact_title(artifact)}.",
            topic=topic,
        )

    def _compose_document_answer(
        self,
        user_input: str,
        artifact: Any,
        notes: str,
        bootstrap: Optional[OrchestratorBootstrapContext] = None,
    ) -> str:
        """Generate a natural answer grounded in one saved document."""
        bootstrap = bootstrap or self.orchestrator.bootstrap_loader.load_context(self.user_id)
        history = self.memory_service.get_history(self.user_id)[-8:]
        student = bootstrap.student_model
        title = self._artifact_title(artifact)
        topic = artifact.topic or "unknown topic"

        system_prompt = f"""
{bootstrap.teacher_soul}

## Identity Layer
{bootstrap.identity_text}

## Teaching Layer
{bootstrap.teaching_text}

## Learner Context
{self._format_student_model_context(student)}

You are answering from one saved study document.
Document title: {title}
Topic folder: {topic}

Use the document notes below as the primary evidence.
If the notes do not contain enough detail, say that plainly, then separate any reasonable inference from the saved notes.
Answer the learner's exact question directly. Do not list files or tell the learner to ask again.
If the learner misspells a technical term, infer the likely intended term.

## Saved Document Notes
{notes[:6500]}
""".strip()

        try:
            response = self.session_response_service.client.messages.create(
                model=self.session_response_service.model,
                max_tokens=800,
                system=system_prompt,
                messages=history or [{"role": "user", "content": user_input}],
            )
            text = "".join(
                block.text for block in response.content if hasattr(block, "text") and block.text
            ).strip()
            if text:
                return text
        except Exception as exc:
            return f"I found the saved document, but hit a runtime error while answering from it: {exc}"

        return "I found the saved document, but I could not generate a grounded answer from its notes."

    def _handle_active_explanation(self, user_input: str) -> List[str]:
        """Continue a real explanation session."""
        outputs: List[str] = []
        post_action = self.explanation_handler.handle(
            self.user_id,
            user_input,
            self._collector(outputs),
        )
        rendered = [f"Sofico: {message}" for message in outputs]
        for message in outputs:
            self.memory_service.add_message(self.user_id, "assistant", message)

        if post_action and post_action.get("action") == "end":
            self._set_focus_topic(post_action.get("topic", ""), source_message=user_input)
        elif post_action and post_action.get("action") == "quiz":
            if post_action.get("scope_type") == "document":
                rendered.extend(self._start_review_session("quiz me on this paper"))
            else:
                rendered.extend(self._start_review_session(f"quiz me on {post_action.get('topic') or self._focused_topic() or ''}"))
        elif post_action and post_action.get("action") == "customize":
            rendered.append("Sofico: Tell me what you want me to change about how I teach.")
        return rendered

    def _execute_ingest(self, user_input: str, requested_followup: Optional[str] = None) -> List[str]:
        """Run pasted-text ingestion through the existing upload pipeline."""
        content = self._extract_ingest_content(user_input)
        if len(content.strip()) < 80:
            message = (
                "Sofico: I need more text to turn that into notes and study questions. "
                "Paste a larger block, or use /paste and finish with a line containing only END."
            )
            self.memory_service.add_message(self.user_id, "assistant", self._strip_transport_prefix(message))
            return [message]

        outputs = self._ingest_text(content)
        ingest_result = self.state.metadata.get("last_ingest_result")
        self._update_focus_from_ingest(ingest_result, source_message=user_input)
        self._remember_ingest_followup(ingest_result, requested_followup=requested_followup)
        if ingest_result and ingest_result.get("status") == "pending_confirmation":
            outputs.append("Sofico: I’m waiting for a save-location answer before I can continue with this document.")
            return outputs
        outputs.extend(self._maybe_continue_after_ingest(ingest_result, requested_followup=requested_followup))
        return outputs

    def _ingest_text(self, content: str) -> List[str]:
        """Run ingestion and cache the saved-topic metadata when available."""
        raw_outputs: List[str] = []
        ingest_result = self.upload_handler.process_text(content, self.user_id, self._collector(raw_outputs))
        self.state.metadata["last_ingest_result"] = ingest_result
        for message in raw_outputs:
            self.memory_service.add_message(self.user_id, "assistant", message)
        return [f"Sofico: {message}" for message in raw_outputs]

    def _compose_teacher_reply(
        self,
        user_input: str,
        capability: str,
        bootstrap: Optional[OrchestratorBootstrapContext] = None,
    ) -> str:
        """Generate a local Sofico reply using the teacher and learner context."""
        bootstrap = bootstrap or self.orchestrator.bootstrap_loader.load_context(self.user_id)
        history = self.memory_service.get_history(self.user_id)[-10:]
        available_topics = self.data_service.get_available_topics(self.user_id)
        matched_topic = self._resolve_topic(user_input, available_topics)
        topic_notes = self.data_service.get_topic_notes(self.user_id, matched_topic) if matched_topic else ""
        memory_context = self.memory_service.get_memory_context(self.user_id)

        student = bootstrap.student_model
        learner_name = (
            student.identity.get("preferred_form_of_address")
            or student.identity.get("learner_name")
            or "the learner"
        )
        study_goals = ", ".join(student.goals_and_constraints.get("study_goals", []) or []) or "not yet specified"
        learning_preferences = ", ".join(student.stated_preferences_about_self.get("learning_preferences", []) or []) or "not yet specified"
        available_topics_text = ", ".join(available_topics) if available_topics else "none yet"
        mode_instruction = (
            "The learner is explicitly asking for an explanation. Teach clearly and directly."
            if capability == "explain"
            else "Respond naturally and conversationally. Help them think, clarify, and learn."
        )

        notes_block = ""
        if topic_notes:
            notes_block = f"\n## Relevant Saved Notes ({matched_topic})\n{topic_notes[:5000]}\n"

        system_prompt = f"""
{bootstrap.teacher_soul}

## Identity Layer
{bootstrap.identity_text}

## Teaching Layer
{bootstrap.teaching_text}

## Learner Context
- learner_name: {learner_name}
- study_goals: {study_goals}
- learning_preferences: {learning_preferences}
- available_topics: {available_topics_text}

## Student Model
{self._format_student_model_context(student)}

## Session Memory
{memory_context or "No summarized session memory yet."}

{mode_instruction}

Rules:
- Sound like Sofico, not like a menu or a customer support script.
- Use the learner context naturally when it helps.
- If the learner mentions or implies a saved topic and relevant notes are available, use them.
- If you are uncertain, say so plainly.
- Be concise by default, but not abrupt.
- No stage directions, no JSON, no backend talk.
{notes_block}
""".strip()

        try:
            response = self.session_response_service.client.messages.create(
                model=self.session_response_service.model,
                max_tokens=700,
                system=system_prompt,
                messages=history,
            )
            text = "".join(
                block.text for block in response.content if hasattr(block, "text") and block.text
            ).strip()
        except Exception as exc:
            text = f"I hit a runtime error while trying to answer that: {exc}"

        self.memory_service.add_message(self.user_id, "assistant", text)
        return text

    def _resolve_topic(self, user_input: str, available_topics: List[str]) -> Optional[str]:
        """Find the most relevant saved topic for this message when possible."""
        lowered = user_input.lower()
        if any(token in lowered for token in ("this", "it", "that", "article", "paper", "text", "section")):
            focused_topic = self._focused_topic()
            if focused_topic:
                return focused_topic
        for topic in available_topics:
            if topic.lower() in lowered:
                return topic
        if len(available_topics) == 1 and self._looks_like_learning_question(user_input):
            return available_topics[0]
        if not available_topics:
            return None
        try:
            return self.session_response_service.resolve_topic(user_input, available_topics)
        except Exception:
            return None

    def _extract_ingest_content(self, user_input: str) -> str:
        """Strip common ingestion prefixes while keeping the main content."""
        lowered = user_input.lower()
        prefixes = [
            "process this:",
            "process this",
            "make notes from this:",
            "make notes from this",
            "turn this into study materials:",
            "turn this into study materials",
            "create a study doc:",
            "create a study doc",
        ]
        for prefix in prefixes:
            if lowered.startswith(prefix):
                return user_input[len(prefix):].strip()
        return user_input

    def _start_capture(
        self,
        intent: str,
        source_request: str,
        initial_lines: Optional[List[str]] = None,
    ) -> List[str]:
        """Start buffered multi-line paste capture."""
        self.capture_state = PasteCaptureState(
            intent=intent,
            source_request=source_request,
            lines=list(initial_lines or []),
        )
        return [
            "Sofico: Paste the full text below. I’ll keep collecting it into one buffer.\n"
            "Type END, done, finish, or process now on its own line when you're done, or /cancel to abort."
        ]

    def _finalize_capture(self) -> List[str]:
        """Process the current capture buffer once the learner finishes pasting."""
        capture = self.capture_state
        self.capture_state = None
        if not capture:
            return []

        content = "\n".join(capture.lines).strip()
        if not content:
            return ["Sofico: I didn’t receive any text in that paste buffer."]

        outputs = self._ingest_text(content)
        ingest_result = self.state.metadata.get("last_ingest_result")
        self._update_focus_from_ingest(
            ingest_result,
            source_message=capture.source_request or content[:120],
        )
        followup = "explain" if capture.intent == "explain" else None
        self._remember_ingest_followup(ingest_result, requested_followup=followup)
        outputs.extend(self._maybe_continue_after_ingest(ingest_result, requested_followup=followup))
        return outputs

    def _infer_capture_intent(self, user_input: str) -> str:
        """Infer whether the next pasted block is mainly for explanation or ingestion."""
        lowered = user_input.lower()
        if any(phrase in lowered for phrase in ("explain this article", "explain this text", "explain this paper")):
            return "explain"
        return "ingest_material"

    def _should_start_capture(self, user_input: str, capability: str) -> bool:
        """Return True when the learner is clearly asking about a text they have not yet provided."""
        lowered = user_input.lower()
        if capability != "explain":
            return False
        if self.document_resolver.matching_artifacts(self.user_id, user_input):
            return False
        if self._focused_topic() and self._references_current_material(lowered):
            return False
        article_signals = (
            "this article",
            "this text",
            "this paper",
            "this essay",
            "the article",
            "the paper",
            "the text",
        )
        return any(signal in lowered for signal in article_signals)

    def _references_current_material(self, lowered_input: str) -> bool:
        """Return True when the learner refers to already-provided material."""
        current_signals = (
            "just gave you",
            "just uploaded",
            "just saved",
            "article i gave",
            "paper i gave",
            "document i gave",
            "from the article",
            "from this article",
            "from the paper",
            "from this paper",
            "from the document",
            "from this document",
        )
        return any(signal in lowered_input for signal in current_signals)

    def _try_start_explanation(self, user_input: str, target: dict = None) -> List[str]:
        """Start explanation from explicit topic or current focus when possible."""
        artifact = self._resolve_explanation_artifact(user_input, target)
        if artifact:
            return self._start_document_explanation_session(artifact, user_input)

        available_topics = self.data_service.get_available_topics(self.user_id)
        resolved_topic = self._resolve_topic(user_input, available_topics)

        if not resolved_topic and target:
            hint = str((target.get("topic") or target.get("document_hint") or "")).strip()
            if hint:
                resolved_topic = self._resolve_topic(hint, available_topics)

        lowered = user_input.lower()
        if not resolved_topic and (
            any(token in lowered for token in ("this", "it", "that", "article", "paper", "text", "notes"))
            or self._is_bare_explain_request(lowered)
        ):
            resolved_topic = self._focused_topic()

        if not resolved_topic:
            return []

        return self._start_explanation_session(resolved_topic)

    def _resolve_explanation_artifact(self, user_input: str, target: dict = None) -> Optional[Any]:
        """Resolve a document-scoped explanation target from the learner turn or current focus."""
        return self.document_resolver.resolve_for_explanation(
            self.user_id,
            user_input,
            self.state.current_focus,
            target=target,
            references_current_material=self._references_current_material(user_input.lower()),
            bare_explain_request=self._is_bare_explain_request(user_input.lower()),
        )

    def _is_bare_explain_request(self, lowered_input: str) -> bool:
        """Return True when the learner asks to explain the current focus without naming it."""
        text = lowered_input.strip()
        return text in {
            "explain",
            "explain it",
            "explain this",
            "first explain",
            "start explaining",
            "walk me through it",
            "walk me through this",
            "notes",
            "notes please",
            "show notes",
            "show me notes",
            "show me the notes",
            "give me notes",
            "give me the notes",
        }

    def _start_explanation_session(self, topic: str) -> List[str]:
        """Start a real explanation session using the existing explanation handler."""
        raw_outputs: List[str] = []
        self.explanation_handler.start(
            self.user_id,
            topic,
            self._collector(raw_outputs),
            learner_brief=self._current_learner_brief(),
        )
        self._set_focus_topic(topic, source_message=f"explain {topic}")
        self._remember_activity(
            kind="explain",
            summary=f"Started explaining {topic}.",
            topic=topic,
        )
        rendered = [f"Sofico: {message}" for message in raw_outputs]
        for message in raw_outputs:
            self.memory_service.add_message(self.user_id, "assistant", message)
        return rendered

    def _start_document_explanation_session(self, artifact: Any, user_input: str) -> List[str]:
        """Start an explanation session grounded in one exact saved document."""
        notes = self._load_artifact_notes(artifact)
        if not notes:
            return []

        raw_outputs: List[str] = []
        title = self._artifact_title(artifact)
        topic = (artifact.topic or "").strip()
        doc_name = self._artifact_doc_name(artifact)
        lowered = user_input.lower().strip()
        initial_message = "" if self._is_bare_explain_request(lowered) else user_input

        self.explanation_handler.start_document(
            self.user_id,
            artifact_title=title,
            topic=topic,
            doc_name=doc_name,
            notes_only=notes,
            say=self._collector(raw_outputs),
            initial_user_message=initial_message,
            learner_brief=self._current_learner_brief(),
        )
        self._set_focus_artifact(artifact, user_input)
        self._remember_activity(
            kind="explain",
            summary=f"Started explaining {title}.",
            topic=topic,
        )
        rendered = [f"Sofico: {message}" for message in raw_outputs]
        for message in raw_outputs:
            self.memory_service.add_message(self.user_id, "assistant", message)
        return rendered

    def _focused_topic(self) -> Optional[str]:
        """Return the topic currently held in focus, if any."""
        topic = (self.state.current_focus.topic or "").strip()
        return topic or None

    def _resolve_review_topic(self, user_input: str) -> Optional[str]:
        """Resolve which topic a quiz request should use."""
        available_topics = self.data_service.get_available_topics(self.user_id)
        resolved_topic = self._resolve_topic(user_input, available_topics)
        if resolved_topic:
            return resolved_topic

        lowered = user_input.lower()
        focus_signals = (
            "quiz me",
            "test me",
            "review this",
            "review it",
            "practice this",
            "practice it",
        )
        if any(signal in lowered for signal in focus_signals):
            focused_topic = self._focused_topic()
            if focused_topic:
                return focused_topic
        return None

    def _resolve_artifact_topic(self, user_input: str) -> Optional[str]:
        """Resolve which saved topic an artifact-inspection request refers to."""
        lowered = user_input.lower()
        available_topics = self.data_service.get_available_topics(self.user_id)
        for topic in available_topics:
            normalized_topic = topic.lower().replace("-", " ").replace("_", " ")
            if topic.lower() in lowered or normalized_topic in lowered:
                return topic

        if self.orchestrator.is_material_inventory_request(lowered):
            return None

        if self._is_folder_document_followup(lowered):
            focused_topic = self._focused_topic()
            if focused_topic:
                return focused_topic

        resolved_topic = self._resolve_topic(user_input, available_topics)
        if resolved_topic:
            return resolved_topic

        focus_signals = (
            "this",
            "it",
            "that",
            "paper",
            "article",
            "document",
            "upload",
            "create",
            "created",
            "saved",
            "notes",
            "questions",
            "key concepts",
        )
        if any(signal in lowered for signal in focus_signals):
            focused_topic = self._focused_topic()
            if focused_topic:
                return focused_topic
        return None

    def _should_show_artifact_context(self, user_input: str) -> bool:
        """Return True when a conversational turn is really about saved materials."""
        lowered = user_input.lower()
        if self._is_folder_document_followup(lowered):
            return True
        return bool(self._matching_artifacts(user_input))

    def _is_folder_document_followup(self, lowered_input: str) -> bool:
        """Return True for follow-ups about other documents in the current folder."""
        folder_followups = (
            "another paper",
            "other paper",
            "another document",
            "other document",
            "in that folder",
            "in this folder",
            "in the folder",
            "do you not see",
            "in the title",
        )
        return any(phrase in lowered_input for phrase in folder_followups)

    def _matching_artifacts(self, user_input: str) -> List[Any]:
        """Find saved artifacts whose title/path matches meaningful words in the turn."""
        return self.document_resolver.matching_artifacts(self.user_id, user_input)

    def _artifact_query_terms(self, user_input: str) -> List[str]:
        """Extract content words useful for matching saved artifact titles."""
        stop_words = {
            "what",
            "about",
            "there",
            "is",
            "are",
            "another",
            "other",
            "paper",
            "papers",
            "document",
            "documents",
            "folder",
            "that",
            "this",
            "the",
            "in",
            "it",
            "do",
            "you",
            "not",
            "see",
            "title",
            "have",
            "has",
            "with",
            "for",
            "look",
            "into",
            "says",
            "said",
            "asked",
            "ask",
            "answer",
            "answers",
            "question",
            "questions",
            "exactly",
            "give",
            "gives",
            "rise",
            "arise",
            "arises",
        }
        normalized = (
            user_input.lower()
            .replace("-", " ")
            .replace("_", " ")
            .replace("?", " ")
            .replace(",", " ")
            .replace(".", " ")
        )
        terms: List[str] = []
        for token in normalized.split():
            if len(token) < 4 or token in stop_words:
                continue
            terms.append(token)
            if len(token) >= 10:
                terms.append(token[:12])
                terms.append(token[:-3])
        return list(dict.fromkeys(term for term in terms if len(term) >= 4))

    def _recall_recent_context(self, intent: str = "") -> str:
        """Answer what we were doing, or render the learner's profile for self-inquiries."""
        # LLM intent is the primary signal — use it directly when available.
        if intent == "user_self_inquiry":
            return self._render_user_profile()

        # Fallback: keyword detection on the most recent user message.
        history = self.memory_service.get_history(self.user_id)
        last_user_msg = next(
            (m.get("content", "") for m in reversed(history) if m.get("role") == "user"), ""
        )
        self_inquiry_signals = (
            "what do you know about me",
            "what you know about me",
            "what do you remember about me",
            "what do you remember",
            "remember about me",
            "tell me about me",
            "tell me about yourself",
            "who am i",
            "what am i",
            "my profile",
            "my persona",
            "about my persona",
            "my learning profile",
            "my learning history",
            "my goals",
            "what are my goals",
            "about yourself",
        )
        if any(signal in last_user_msg.lower() for signal in self_inquiry_signals):
            return self._render_user_profile()

        focus = self.state.current_focus
        metadata = self.state.metadata or {}
        memory = self.data_service.load_memory(self.user_id)
        sessions = memory.get("session_history", []) if isinstance(memory, dict) else []

        parts: list[str] = []

        # Most recent meaningful activity (quiz / explain / research take priority
        # over document_answer — see _ACTIVITY_PRIORITY in _set_activity_metadata)
        last_summary = metadata.get("last_activity_summary", "")
        last_kind = metadata.get("last_activity_kind", "")
        if last_summary:
            parts.append(last_summary)

        # Current focus — only add doc_title if it's not already in last_summary
        if focus and focus.topic:
            doc_title = (focus.metadata or {}).get("document_title", "")
            if doc_title and doc_title.lower() not in (last_summary or "").lower():
                parts.append(f"We were looking at *{doc_title}*.")
            elif not doc_title and (last_kind not in ("explain", "review") or not last_summary):
                parts.append(f"Last topic: *{focus.topic}*.")

        # Previous session summary — only show if there's nothing more recent above
        if not parts and sessions:
            latest_session = sessions[-1]
            summary = latest_session.get("summary", "")
            topics_str = ", ".join(latest_session.get("topics", []) or [])
            if summary:
                label = f"From last session ({topics_str})" if topics_str else "From last session"
                parts.append(f"{label}: {summary}")

        if not parts:
            available_topics = [
                t for t in (self.data_service.get_available_topics(self.user_id) or [])
                if len(t) <= 60
            ]
            if available_topics:
                return "I don't have a recent activity breadcrumb, but your saved topics are: " + ", ".join(available_topics[-8:]) + ". Want to pick up where we left off?"
            return "I don't have anything saved about recent activity yet — what would you like to work on?"

        response = " ".join(parts)
        if focus and focus.topic:
            response += "\n\nWant to continue? Say `explain it`, `quiz me`, or `show my notes`."
        return response

    def _render_user_profile(self) -> str:
        """Render what Sofi knows about the learner in her own voice."""
        bootstrap = self.orchestrator.bootstrap_loader.load_context(self.user_id)
        student = bootstrap.student_model
        identity = getattr(student, "identity", {}) or {}
        goals = getattr(student, "goals_and_constraints", {}) or {}
        preferences = getattr(student, "stated_preferences_about_self", {}) or {}
        inferred = [
            entry.summary
            for entry in getattr(student, "inferred_profile", []) or []
            if getattr(entry, "status", "active") == "active" and getattr(entry, "summary", "")
        ]
        relationship = [
            entry.summary
            for entry in getattr(student, "relationship_memory", []) or []
            if getattr(entry, "status", "active") == "active" and getattr(entry, "summary", "")
        ]

        name = (
            identity.get("preferred_form_of_address")
            or identity.get("learner_name")
            or "you"
        )
        lines = [f"Here's what I have saved about *{name}*:", ""]

        goal_list = goals.get("study_goals") or []
        if goal_list:
            lines.append(f"- Study goals: {', '.join(goal_list)}")

        subjects = goals.get("preferred_subjects") or []
        if subjects:
            lines.append(f"- Preferred subjects: {', '.join(subjects)}")

        prefs = preferences.get("learning_preferences") or []
        if prefs:
            lines.append(f"- Learning preferences: {', '.join(prefs)}")

        if inferred:
            lines.append(f"- What I've noticed: {'; '.join(inferred[-3:])}")

        if relationship:
            lines.append(f"- About our sessions: {'; '.join(relationship[-2:])}")

        available_topics = [
            t for t in (self.data_service.get_available_topics(self.user_id) or [])
            if len(t) <= 60
        ]
        if available_topics:
            lines.append(f"- Saved topics: {', '.join(available_topics[:8])}")

        if len(lines) <= 2:
            return "I don't have much saved about you yet — tell me about yourself and I'll remember it."

        lines += ["", "Want to tell me something else, or shall we get back to studying?"]
        return "\n".join(lines)

    def _should_continue_from_focus(self, user_input: str) -> bool:
        """Treat natural follow-up questions as explanation on the focused topic."""
        if not self._focused_topic():
            return False
        lowered = user_input.lower()
        follow_up_signals = (
            "why",
            "how",
            "what",
            "can you",
            "could you",
            "explain",
            "go deeper",
            "say more",
            "what about",
            "i don't get",
            "i dont get",
            "i still don't understand",
            "i still dont understand",
            "this",
            "it",
            "that",
            "part",
            "section",
        )
        return any(signal in lowered for signal in follow_up_signals) and self._looks_like_learning_question(user_input)

    def _looks_like_learning_question(self, user_input: str) -> bool:
        """Heuristic for learner turns that are probably asking for understanding."""
        text = user_input.strip()
        lowered = text.lower()
        if "?" in text:
            return True
        starters = (
            "why",
            "how",
            "what",
            "can you",
            "could you",
            "please explain",
            "tell me more",
            "go deeper",
            "say more",
            "walk me through",
            "help me understand",
            "i don't understand",
            "i dont understand",
        )
        return any(lowered.startswith(starter) for starter in starters)

    def _refresh_focus_from_message(self, user_input: str):
        """Keep focus aligned with the latest named topic in natural conversation."""
        available_topics = self.data_service.get_available_topics(self.user_id)
        resolved_topic = self._resolve_topic(user_input, available_topics)
        if resolved_topic:
            self._set_focus_topic(resolved_topic, source_message=user_input)

    def _update_focus_from_ingest(self, ingest_result: Optional[dict], source_message: str):
        """Update current focus after successful ingestion."""
        if not ingest_result or ingest_result.get("status") not in {"saved", "duplicate"}:
            return
        topic = (ingest_result.get("topic") or "").strip()
        self._clear_active_learning_modes()
        self._apply_topic_focus(
            topic,
            source_message,
            {
                "from_ingest": True,
                "question_count": ingest_result.get("question_count", 0),
                "doc_name": ingest_result.get("doc_name", ""),
            },
        )

    def _apply_topic_focus(self, topic: str, source_message: str, metadata: dict):
        """Find the best notes artifact for a topic and set it as current focus."""
        if not topic:
            return
        notes_artifact_id = ""
        requested_doc_name = str(metadata.get("doc_name", "") or "").strip()
        topic_artifacts = self.artifact_store.find_by_topic(self.user_id, topic)

        if requested_doc_name:
            for artifact in reversed(topic_artifacts):
                if artifact.artifact_type.value != "notes":
                    continue
                artifact_doc_name = self._artifact_doc_name(artifact)
                if artifact_doc_name == requested_doc_name or Path(artifact_doc_name).stem == Path(requested_doc_name).stem:
                    notes_artifact_id = artifact.artifact_id
                    break

        if not notes_artifact_id:
            for artifact in reversed(topic_artifacts):
                if artifact.artifact_type.value == "notes":
                    notes_artifact_id = artifact.artifact_id
                    break
        self.state.current_focus = CurrentFocus(
            kind=FocusKind.ARTIFACT if notes_artifact_id else FocusKind.TOPIC,
            artifact_id=notes_artifact_id,
            topic=topic,
            source_message=source_message[:200],
            updated_at=self._now_iso(),
            metadata=metadata,
        )
        if metadata.get("from_ingest") or metadata.get("resolved_after_pending_confirmation"):
            question_count = metadata.get("question_count")
            count_text = f" with {question_count} questions" if question_count else ""
            self._set_activity_metadata(
                kind="ingest",
                summary=f"Saved new study material under {topic}{count_text}.",
                topic=topic,
            )
        self._persist_conversation_state()

    def _set_focus_topic(self, topic: str, source_message: str):
        """Set current focus to a resolved topic."""
        if not topic:
            return
        self.state.current_focus = CurrentFocus(
            kind=FocusKind.TOPIC,
            topic=topic,
            source_message=source_message[:200],
            updated_at=self._now_iso(),
            metadata={"manually_set": True},
        )
        self._persist_conversation_state()

    def _remember_activity(self, kind: str, summary: str, topic: str = ""):
        """Persist a short breadcrumb about the latest meaningful work."""
        self._set_activity_metadata(kind=kind, summary=summary, topic=topic)
        self._persist_conversation_state()

    # Activities ordered by importance — lower-ranked kinds cannot overwrite higher ones.
    _ACTIVITY_PRIORITY = {
        "explain": 3,
        "review": 3,
        "curriculum": 3,
        "research": 2,
        "document_answer": 1,
        "document_inventory": 1,
        "document_profile": 1,
    }

    def _set_activity_metadata(self, kind: str, summary: str, topic: str = ""):
        """Update recent activity metadata, but never let a low-priority event
        overwrite a high-priority one from the same session.

        document_answer fires whenever Sofi cites a saved paper in any reply.
        Without this guard it overwrites "Started a quiz on X" the moment the
        learner asks a follow-up question, making recall_context look stale.
        """
        current_kind = self.state.metadata.get("last_activity_kind", "")
        current_priority = self._ACTIVITY_PRIORITY.get(current_kind, 0)
        new_priority = self._ACTIVITY_PRIORITY.get(kind, 0)
        if new_priority < current_priority:
            return
        self.state.metadata["last_activity_kind"] = kind
        self.state.metadata["last_activity_summary"] = summary
        self.state.metadata["last_activity_topic"] = topic
        self.state.metadata["last_activity_at"] = self._now_iso()

    def _now_iso(self) -> str:
        """Timestamp helper for focus updates."""
        return datetime.now().isoformat(timespec="seconds")

    def _should_auto_capture(self, user_input: str, capability: str) -> bool:
        """Return True when a turn looks like a partial pasted article or essay chunk."""
        text = user_input.strip()
        lowered = text.lower()
        if capability not in {"converse", "explain", "ingest_material"}:
            return False
        if lowered.startswith("/"):
            return False
        if self.document_resolver.matching_artifacts(self.user_id, user_input):
            return False

        truncated_endings = (
            text.endswith(",")
            or text.endswith(";")
            or text.endswith(":")
            or text.endswith("-")
            or (text and text[-1].isalnum() and not text.endswith((".", "!", "?", "\"", "'", "`", ")", "]")))
        )

        article_cues = (
            "introduction:",
            "part i",
            "part ii",
            "abstract:",
            "this article",
            "looking back",
            "the results were remarkable",
        )

        article_heading = (
            any(lowered.startswith(cue) for cue in ("introduction:", "part i", "part ii", "abstract:", "conclusion:"))
            or (
                len(text) >= 20
                and len(text) <= 120
                and text == text.strip()
                and text.count(".") <= 1
                and text.count("\n") == 0
                and any(cue in lowered for cue in article_cues)
            )
        )

        if article_heading:
            return True
        if capability == "ingest_material" and len(text) >= 250:
            return True
        if len(text) < 350:
            return False

        sentence_markers = text.count(". ") + text.count("?\n") + text.count("!\n") + text.count("\n\n")
        if sentence_markers < 2:
            return False

        return truncated_endings or any(cue in lowered for cue in article_cues)

    def _collector(self, outputs: List[str]) -> Callable[[str], None]:
        """Return a simple callback that collects handler output."""

        def say(message: str, **_: object):
            outputs.append(message)

        return say

    def _is_batch_confirmation(self, lowered: str) -> bool:
        """Return True when the learner confirms a pending batch of operations."""
        confirm_words = {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "go", "go ahead", "do it", "proceed", "confirm", "all good", "correct", "that's right", "thats right", "sounds good"}
        return lowered in confirm_words or lowered.startswith(("yes ", "go ahead"))

    def _is_batch_cancellation(self, lowered: str) -> bool:
        """Return True when the learner cancels a pending batch of operations."""
        cancel_words = {"no", "n", "cancel", "stop", "abort", "never mind", "nevermind", "nope", "don't", "dont"}
        return lowered in cancel_words or lowered.startswith("no ")

    def _execute_pending_batch_ops(self) -> List[str]:
        """Execute each stored operation in order and return all result messages."""
        ops = list(self.state.metadata.pop("pending_batch_ops", []))
        outputs: List[str] = []
        for op in ops:
            capability = str(op.get("capability", ""))
            try:
                if capability == "move_document":
                    result = self.document_library_service.move_document(
                        user_id=self.user_id,
                        user_input="",
                        current_focus=self.state.current_focus,
                        target=op,
                    )
                    if result.get("state_delta"):
                        self._apply_execution_state(result["state_delta"])
                elif capability == "rename_document":
                    result = self.document_library_service.rename_document(
                        user_id=self.user_id,
                        user_input="",
                        current_focus=self.state.current_focus,
                        target=op,
                    )
                    if result.get("state_delta"):
                        self._apply_execution_state(result["state_delta"])
                elif capability == "delete_topic":
                    result = self.document_library_service.delete_topic(
                        user_id=self.user_id,
                        topic=str(op.get("topic") or "").strip(),
                    )
                else:
                    # BatchConfirmExecutor already filtered non-document ops, so this
                    # branch is defensive — silently skip rather than expose internal
                    # capability names to the learner.
                    continue
                msg = result.get("message") or ""
            except Exception as exc:
                msg = f"Something went wrong with that operation: {exc}"
            if msg:
                outputs.append(f"Sofico: {msg}")
                self.memory_service.add_message(self.user_id, "assistant", msg)
        return outputs or ["Sofico: Done — all changes applied."]

    def _handle_pending_ingest_confirmation(self, user_input: str) -> List[str]:
        """Continue an upload workflow that is waiting on folder/topic confirmation."""
        pending_followup = self._extract_pending_followup_intent(user_input)
        if pending_followup:
            self.state.metadata["pending_ingest_followup"] = pending_followup
            self._persist_conversation_state()
            message = (
                "Sofico: I still need to save this document first. "
                "Say yes to merge, no to create a new topic, or tell me the folder name. "
                "After that I’ll explain it."
            )
            self.memory_service.add_message(self.user_id, "assistant", self._strip_transport_prefix(message))
            return [message]

        pending_question = self._answer_pending_topic_question(user_input)
        if pending_question:
            self.memory_service.add_message(self.user_id, "assistant", self._strip_transport_prefix(pending_question))
            return [pending_question]

        before_artifacts = self.artifact_store.list_artifacts(self.user_id)
        before_ids = {artifact.artifact_id for artifact in before_artifacts}
        before_topics = set(self.data_service.get_available_topics(self.user_id))

        raw_outputs: List[str] = []
        self.upload_handler.handle_pending(self.user_id, user_input, self._collector(raw_outputs))
        rendered = [f"Sofico: {message}" for message in raw_outputs]
        for message in raw_outputs:
            self.memory_service.add_message(self.user_id, "assistant", message)

        pending_followup = self.state.metadata.get("pending_ingest_followup", "")
        if self.upload_handler.has_pending(self.user_id):
            return rendered

        saved_topic = self._infer_saved_topic_after_pending(before_ids, before_topics)
        if not saved_topic:
            self.state.metadata.pop("pending_ingest_followup", None)
            return rendered

        self._clear_active_learning_modes()
        self._apply_topic_focus(
            saved_topic,
            source_message=user_input,
            metadata={"resolved_after_pending_confirmation": True},
        )
        self.state.metadata.pop("pending_ingest_followup", None)
        if pending_followup == "explain":
            rendered.extend(self._start_explanation_session(saved_topic))
        return rendered

    def _remember_ingest_followup(self, ingest_result: Optional[dict], requested_followup: Optional[str]):
        """Persist the learner's next desired action across delayed upload confirmation."""
        if not requested_followup:
            self.state.metadata.pop("pending_ingest_followup", None)
            self._persist_conversation_state()
            return
        if ingest_result and ingest_result.get("status") == "pending_confirmation":
            self.state.metadata["pending_ingest_followup"] = requested_followup
            self._persist_conversation_state()
        elif ingest_result and ingest_result.get("status") == "saved":
            self.state.metadata.pop("pending_ingest_followup", None)
            self._persist_conversation_state()

    def _maybe_continue_after_ingest(
        self,
        ingest_result: Optional[dict],
        requested_followup: Optional[str],
    ) -> List[str]:
        """Chain ingestion into the next action when the learner's intent is clear."""
        if requested_followup != "explain":
            return []
        if not ingest_result or ingest_result.get("status") != "saved":
            return []
        topic = (ingest_result.get("topic") or "").strip()
        if topic:
            return self._start_explanation_session(topic)
        return []

    def _infer_saved_topic_after_pending(
        self,
        before_ids: set[str],
        before_topics: set[str],
    ) -> Optional[str]:
        """Infer which topic was saved after a pending confirmation response."""
        after_artifacts = self.artifact_store.list_artifacts(self.user_id)
        new_artifacts = [artifact for artifact in after_artifacts if artifact.artifact_id not in before_ids]
        notes_artifacts = [
            artifact for artifact in new_artifacts if artifact.artifact_type.value == "notes" and artifact.topic
        ]
        if notes_artifacts:
            notes_artifacts.sort(key=lambda artifact: artifact.created_at or "")
            return notes_artifacts[-1].topic

        after_topics = set(self.data_service.get_available_topics(self.user_id))
        new_topics = sorted(after_topics - before_topics)
        if new_topics:
            return new_topics[-1]

        focused_topic = self._focused_topic()
        return focused_topic or None

    def _extract_pending_followup_intent(self, user_input: str) -> Optional[str]:
        """Detect a follow-up request made before the pending document is saved."""
        lowered = user_input.lower().strip()
        explain_signals = (
            "explain it",
            "explain this",
            "explain the paper",
            "explain the article",
            "first explain",
            "then explain",
            "and then explain",
        )
        if any(signal in lowered for signal in explain_signals):
            return "explain"
        return None

    def _answer_pending_topic_question(self, user_input: str) -> str:
        """Answer conversational questions while a save-location decision is pending."""
        lowered = user_input.lower().strip()
        question_signals = (
            "what do you think",
            "same topic",
            "is it the same",
            "does it belong",
            "should i",
            "where should",
            "what would you",
            "do you think",
        )
        if not any(signal in lowered for signal in question_signals):
            return ""

        pending = self.upload_handler.pending_uploads.get(self.user_id)
        if not pending and hasattr(self.upload_handler, "_load_pending_state"):
            pending = self.upload_handler._load_pending_state(self.user_id) or {}
            if pending:
                self.upload_handler.pending_uploads[self.user_id] = pending
        if not pending:
            return ""

        result = pending.get("result", {}) or {}
        suggested_topic = (pending.get("suggested_topic") or "").strip()
        document_topic = (result.get("topic") or "").strip()
        tags = result.get("tags", []) or []
        existing_notes = self.data_service.get_topic_notes(self.user_id, suggested_topic) if suggested_topic else ""

        recommendation = self._pending_topic_recommendation(
            document_topic=document_topic,
            suggested_topic=suggested_topic,
            tags=tags,
            existing_notes=existing_notes,
        )
        return (
            "Sofico: "
            + recommendation
            + "\n\nSay `yes` to merge, `no` to create a new topic, or tell me a different folder name."
        )

    def _pending_topic_recommendation(
        self,
        document_topic: str,
        suggested_topic: str,
        tags: List[str],
        existing_notes: str,
    ) -> str:
        """Give a concise recommendation about a pending upload topic match."""
        tags_text = ", ".join(tags) if tags else "no extracted tags"
        existing_preview = existing_notes[:2500] if existing_notes else "No existing notes preview available."
        prompt = f"""
You are Sofico deciding where to save newly processed study material.

Existing folder suggested by the system: {suggested_topic}
New document topic: {document_topic}
New document tags: {tags_text}

Existing notes preview from suggested folder:
{existing_preview}

Give a concise recommendation: should the learner merge this document into the suggested folder, or create a new topic?
Be direct. Mention uncertainty if needed. Do not pretend you know more than these signals.
Do not finalize the save; the learner still must choose.
""".strip()
        try:
            response = self.session_response_service.client.messages.create(
                model=self.session_response_service.model,
                max_tokens=180,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text for block in response.content if hasattr(block, "text") and block.text
            ).strip()
            if text:
                return text
        except Exception:
            pass

        if suggested_topic and document_topic and (
            suggested_topic in document_topic
            or document_topic in suggested_topic
            or bool(set(suggested_topic.split("-")) & set(document_topic.split("-")))
        ):
            return (
                f"My recommendation: merge it into *{suggested_topic}*. "
                f"The new topic name *{document_topic}* overlaps enough that it looks like the same study area."
            )
        if suggested_topic:
            return (
                f"I am not fully sure from the saved metadata alone. "
                f"The parser saw the new topic as *{document_topic or 'unknown'}* and the closest existing folder is *{suggested_topic}*."
            )
        return "I am not fully sure from the saved metadata alone. Creating a new topic is safer if you want separation."

    def shutdown(self):
        """Persist session state and ask the memory service to summarize the session."""
        self._persist_conversation_state()
        self.memory_service.end_session(self.user_id)

    def _load_conversation_state(self) -> ConversationState:
        """Restore short-lived state that should survive process restarts."""
        raw_state = self.data_service.load_recent_task_state(self.user_id)
        focus = self._focus_from_dict(raw_state.get("current_focus", {}))
        metadata = raw_state.get("metadata", {}) or {}

        # Drop references to topics/documents that no longer exist on disk.
        # Without this, after a wipe or rename the learner sees ghost
        # breadcrumbs ("Last activity: Started explaining <deleted paper>").
        available_topics = set(self.data_service.get_available_topics(self.user_id) or [])
        if focus.topic and focus.topic not in available_topics:
            focus = CurrentFocus()
        last_topic = (metadata.get("last_activity_topic") or "").strip()
        if last_topic and last_topic not in available_topics:
            for key in (
                "last_activity_kind",
                "last_activity_summary",
                "last_activity_topic",
                "last_activity_at",
            ):
                metadata.pop(key, None)

        return ConversationState(
            active_mode=raw_state.get("active_mode", ""),
            pending_action=raw_state.get("pending_action", ""),
            recent_intent=raw_state.get("recent_intent", ""),
            temporary_overrides=raw_state.get("temporary_overrides", {}) or {},
            current_focus=focus,
            updated_at=raw_state.get("updated_at", ""),
            metadata=metadata,
        )

    def _persist_conversation_state(self):
        """Persist lightweight session state for the learner.

        This is not the full chat transcript. It is the control state Sofico needs
        to remember what "it" or "this" means after a restart.
        """
        self.data_service.save_recent_task_state(
            self.user_id,
            {
                "active_mode": self.state.active_mode,
                "pending_action": self.state.pending_action,
                "recent_intent": self.state.recent_intent,
                "temporary_overrides": self.state.temporary_overrides,
                "current_focus": self._focus_to_dict(self.state.current_focus),
                "metadata": self._persistent_metadata(),
                "updated_at": self._now_iso(),
            },
        )

    def _persistent_metadata(self) -> Dict[str, Any]:
        """Return only metadata safe/useful to keep across restarts."""
        keep_keys = {
            "pending_ingest_followup",
            "pending_batch_ops",
            "last_activity_kind",
            "last_activity_summary",
            "last_activity_topic",
            "last_activity_at",
        }
        return {key: value for key, value in self.state.metadata.items() if key in keep_keys}

    def _focus_to_dict(self, focus: CurrentFocus) -> Dict[str, Any]:
        """Serialize current focus to a YAML-safe dictionary."""
        return {
            "kind": focus.kind.value if isinstance(focus.kind, FocusKind) else str(focus.kind or FocusKind.NONE.value),
            "artifact_id": focus.artifact_id,
            "topic": focus.topic,
            "lesson_id": focus.lesson_id,
            "curriculum_id": focus.curriculum_id,
            "source_message": focus.source_message,
            "updated_at": focus.updated_at,
            "metadata": focus.metadata,
        }

    def _focus_from_dict(self, raw_focus: Dict[str, Any]) -> CurrentFocus:
        """Restore current focus from persisted state."""
        if not isinstance(raw_focus, dict):
            return CurrentFocus()
        try:
            kind = FocusKind(raw_focus.get("kind", FocusKind.NONE.value))
        except ValueError:
            kind = FocusKind.NONE
        return CurrentFocus(
            kind=kind,
            artifact_id=raw_focus.get("artifact_id", ""),
            topic=raw_focus.get("topic", ""),
            lesson_id=raw_focus.get("lesson_id", ""),
            curriculum_id=raw_focus.get("curriculum_id", ""),
            source_message=raw_focus.get("source_message", ""),
            updated_at=raw_focus.get("updated_at", ""),
            metadata=raw_focus.get("metadata", {}) or {},
        )

    def _format_student_model_context(self, student: Any) -> str:
        """Create compact student-model context for LLM prompts."""
        parts: List[str] = []

        identity = getattr(student, "identity", {}) or {}
        goals = getattr(student, "goals_and_constraints", {}) or {}
        preferences = getattr(student, "stated_preferences_about_self", {}) or {}

        if identity:
            parts.append(f"- identity: {identity}")
        if goals:
            parts.append(f"- goals_and_constraints: {goals}")
        if preferences:
            parts.append(f"- stated_preferences_about_self: {preferences}")

        for section_name in ("inferred_profile", "progress_patterns", "relationship_memory"):
            entries = [
                entry.summary
                for entry in getattr(student, section_name, []) or []
                if getattr(entry, "status", "active") == "active" and getattr(entry, "summary", "")
            ]
            if entries:
                parts.append(f"- {section_name}: " + "; ".join(entries[-5:]))

        return "\n".join(parts) if parts else "No student model details yet."

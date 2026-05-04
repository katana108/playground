"""OpenClaw-style context engine for Sofico.

The context engine owns what the agent can see before a turn is interpreted.
It is intentionally transport-independent: Slack, CLI, Telegram, or tests can
all provide a TurnContext and receive the same context packet shape.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .artifact_store import ArtifactStore
from .bootstrap_loader import BootstrapLoader, OrchestratorBootstrapContext
from .capability_registry import CapabilityRegistry
from .models import ConversationState, CurrentFocus, StudyArtifact, TurnContext
from .student_model import StudentMemoryEntry, StudentModel


@dataclass
class DocumentContext:
    """One saved document or source file available to Sofico."""

    title: str
    topic: str
    doc_id: str = ""
    source_path: str = ""
    artifact_id: str = ""
    artifact_type: str = ""
    doc_type: str = ""
    authors: List[str] = field(default_factory=list)
    year: int | None = None
    question_count: int = 0
    tags: List[str] = field(default_factory=list)
    source_label: str = ""
    summary_short: str = ""
    notes_ready: bool = False
    quiz_ready: bool = False


@dataclass
class TopicContext:
    """A topic folder and its visible study material."""

    name: str
    question_count: int = 0
    notes_available: bool = False
    documents: List[DocumentContext] = field(default_factory=list)


@dataclass
class ActiveWorkflowContext:
    """Workflow state that may influence how the next turn is interpreted."""

    onboarding_active: bool = False
    pending_upload: bool = False
    curriculum_active: bool = False
    curriculum_subject: str = ""
    explanation_active: bool = False
    explanation_topic: str = ""
    review_active: bool = False
    review_topic: str = ""
    review_question_index: int = 0
    review_question_count: int = 0
    capture_active: bool = False


@dataclass
class SoficoContextPacket:
    """The complete LLM-facing context packet for one turn."""

    turn: Dict[str, Any]
    runtime: Dict[str, Any]
    learner: Dict[str, Any]
    learner_brief: Dict[str, Any]
    teacher: Dict[str, Any]
    focus: Dict[str, Any]
    active_workflows: ActiveWorkflowContext
    recent_messages: List[Dict[str, Any]]
    topics: List[TopicContext]
    capabilities: Dict[str, str]
    tutor: Dict[str, Any] = field(default_factory=dict)
    notes: Dict[str, Any] = field(default_factory=dict)


class SoficoContextEngine:
    """Assemble, compact, and persist context around one Sofico turn."""

    def __init__(
        self,
        bootstrap_loader: BootstrapLoader,
        capability_registry: CapabilityRegistry,
        data_service: Any = None,
        memory_service: Any = None,
        artifact_store: Optional[ArtifactStore] = None,
        learner_brief_service: Any = None,
        max_recent_messages: int = 10,
    ):
        self.bootstrap_loader = bootstrap_loader
        self.capability_registry = capability_registry
        self.data_service = data_service
        self.memory_service = memory_service
        self.artifact_store = artifact_store or ArtifactStore(bootstrap_loader.project_root)
        self.learner_brief_service = learner_brief_service
        self.max_recent_messages = max_recent_messages

    def ingest(self, turn: TurnContext, state: ConversationState) -> Dict[str, Any]:
        """Return intake metadata for the turn.

        Persistence of raw messages remains transport/controller-owned for now,
        so this method is intentionally side-effect free in V1.
        """
        return {
            "user_id": turn.user_id,
            "source": turn.source,
            "message_ts": turn.message_ts,
            "ingested_at": datetime.now().isoformat(timespec="seconds"),
            "active_mode": state.active_mode,
        }

    def assemble(
        self,
        turn: TurnContext,
        state: Optional[ConversationState] = None,
        bootstrap: Optional[OrchestratorBootstrapContext] = None,
        active_workflows: Optional[ActiveWorkflowContext] = None,
    ) -> SoficoContextPacket:
        """Build the context packet for interpreting one turn."""
        state = state or ConversationState()
        bootstrap = bootstrap or self.bootstrap_loader.load_context(turn.user_id)
        active_workflows = active_workflows or ActiveWorkflowContext()
        recent_messages = self._recent_messages(turn.user_id, state)
        topics = self._topic_contexts(turn.user_id)
        learner_brief = {}
        if self.learner_brief_service:
            try:
                learner_brief = self.learner_brief_service.build(
                    turn.user_id,
                    student_model=bootstrap.student_model,
                )
            except Exception:
                learner_brief = {}

        tutor = self._load_tutor_config(turn.user_id)
        return SoficoContextPacket(
            turn={
                "user_id": turn.user_id,
                "message": turn.message,
                "normalized_message": turn.normalized_message,
                "source": turn.source,
                "channel_id": turn.channel_id,
                "message_ts": turn.message_ts,
                "attachments": turn.attachments,
            },
            runtime={
                "assembled_at": datetime.now().isoformat(timespec="seconds"),
                "learner_folder": self.bootstrap_loader.student_model_store.get_learner_folder(turn.user_id),
                "active_mode": state.active_mode,
                "pending_action": state.pending_action,
                "recent_intent": state.recent_intent,
            },
            learner=self._student_summary(bootstrap.student_model),
            learner_brief=learner_brief,
            teacher=self._teacher_summary(bootstrap),
            focus=self._focus_summary(state.current_focus),
            active_workflows=active_workflows,
            recent_messages=recent_messages,
            topics=topics,
            capabilities=self.capability_registry.summarize(),
            tutor=tutor,
            notes={
                "topic_count": len(topics),
                "document_count": sum(len(topic.documents) for topic in topics),
                "recent_message_count": len(recent_messages),
            },
        )

    def compact(self, packet: SoficoContextPacket) -> SoficoContextPacket:
        """Return a compacted packet.

        V1 keeps the packet unchanged. Later this will summarize old messages
        and reduce very large artifact lists.
        """
        return packet

    def after_turn(
        self,
        turn: TurnContext,
        state: ConversationState,
        decision: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return after-turn persistence metadata.

        V1 is side-effect free; controllers still persist focus/memory directly.
        """
        return {
            "user_id": turn.user_id,
            "source": turn.source,
            "decision": decision or {},
            "result": result or {},
            "focus": self._focus_summary(state.current_focus),
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }

    def to_dict(self, packet: SoficoContextPacket) -> Dict[str, Any]:
        """Serialize a context packet for logs, tests, or LLM prompts."""
        return asdict(packet)

    def _recent_messages(self, user_id: str, state: ConversationState) -> List[Dict[str, Any]]:
        stored = list((state.metadata or {}).get("stored_messages", []) or [])
        if not stored and self.memory_service:
            try:
                stored = list(self.memory_service.get_history(user_id))
            except Exception:
                stored = []
        return stored[-self.max_recent_messages :]

    def _topic_contexts(self, user_id: str) -> List[TopicContext]:
        if not self.data_service:
            return []
        try:
            topics = self.data_service.get_available_topics(user_id)
        except Exception:
            topics = []

        artifacts = self._artifacts_by_topic(user_id)
        return [
            self._topic_context(user_id, topic, artifacts.get(topic, []))
            for topic in topics
        ]

    def _topic_context(
        self,
        user_id: str,
        topic: str,
        artifacts: List[StudyArtifact],
    ) -> TopicContext:
        index_data = self._topic_index(user_id, topic)
        questions = index_data.get("questions", []) if isinstance(index_data, dict) else []
        notes = self._topic_notes(user_id, topic)
        docs = self._documents_for_topic(user_id, topic, artifacts, questions)
        return TopicContext(
            name=topic,
            question_count=len(questions),
            notes_available=bool(notes.strip()),
            documents=docs,
        )

    def _documents_for_topic(
        self,
        user_id: str,
        topic: str,
        artifacts: List[StudyArtifact],
        questions: List[Dict[str, Any]],
    ) -> List[DocumentContext]:
        docs_by_path: Dict[str, DocumentContext] = {}
        docs_by_id: Dict[str, DocumentContext] = {}

        for artifact in artifacts:
            source_path = artifact.source_path or artifact.metadata.get("doc_name", "")
            key = source_path or artifact.artifact_id
            title = artifact.title or artifact.metadata.get("source_label") or source_path or artifact.artifact_type.value
            existing = docs_by_path.get(key)
            if existing and existing.artifact_type == "uploaded_source":
                continue
            docs_by_path[key] = DocumentContext(
                title=title,
                topic=topic,
                doc_id=str(artifact.metadata.get("doc_id", "") or ""),
                source_path=source_path,
                artifact_id=artifact.artifact_id,
                artifact_type=artifact.artifact_type.value,
                doc_type=str(artifact.metadata.get("doc_type", "") or ""),
                authors=list(artifact.metadata.get("authors", []) or []),
                year=artifact.metadata.get("year"),
                question_count=int(artifact.metadata.get("question_count", 0) or 0),
                tags=list(artifact.metadata.get("tags", []) or []),
                source_label=artifact.metadata.get("source_label", ""),
                summary_short=str(artifact.metadata.get("summary_short", "") or ""),
                notes_ready=artifact.artifact_type.value in {"notes", "lesson_material"},
                quiz_ready=bool(int(artifact.metadata.get("question_count", 0) or 0)),
            )

        for filename in self._topic_document_names(user_id, topic):
            source_path = f"{topic}/{filename}"
            docs_by_path.setdefault(
                source_path,
                DocumentContext(
                    title=filename.removesuffix(".md"),
                    topic=topic,
                    source_path=source_path,
                    artifact_type="study_document",
                    question_count=self._question_count_for_document(filename, questions),
                    notes_ready=True,
                    quiz_ready=bool(self._question_count_for_document(filename, questions)),
                ),
            )

        for manifest in self._topic_document_manifests(user_id, topic):
            doc_id = str(manifest.get("doc_id", "") or "")
            storage = manifest.get("storage", {}) or {}
            bibliography = manifest.get("bibliography", {}) or {}
            learning = manifest.get("learning", {}) or {}
            knowledge = manifest.get("knowledge", {}) or {}
            source = manifest.get("source", {}) or {}
            primary_path = str(storage.get("legacy_topic_document_path", "") or "")
            source_path = primary_path.replace("topics/", "", 1) if primary_path.startswith("topics/") else primary_path
            enriched = DocumentContext(
                title=str(manifest.get("display_title") or manifest.get("title") or doc_id),
                topic=topic,
                doc_id=doc_id,
                source_path=source_path,
                artifact_type="document_manifest",
                doc_type=str(manifest.get("doc_type", "") or ""),
                authors=list(bibliography.get("authors", []) or []),
                year=bibliography.get("year"),
                question_count=int(learning.get("question_count", 0) or 0),
                tags=list(knowledge.get("keywords", []) or []),
                source_label=str(source.get("source_label", "") or ""),
                summary_short=str(learning.get("summary_short", "") or ""),
                notes_ready=bool(learning.get("explanation_ready", False)),
                quiz_ready=bool(learning.get("quiz_ready", False)),
            )
            if doc_id:
                docs_by_id[doc_id] = enriched
            if source_path:
                docs_by_path[source_path] = enriched

        merged: List[DocumentContext] = list(docs_by_path.values())
        for doc_id, document in docs_by_id.items():
            if doc_id and all(existing.doc_id != doc_id for existing in merged):
                merged.append(document)
        return merged

    def _artifacts_by_topic(self, user_id: str) -> Dict[str, List[StudyArtifact]]:
        grouped: Dict[str, List[StudyArtifact]] = {}
        try:
            artifacts = self.artifact_store.list_artifacts(user_id)
        except Exception:
            artifacts = []
        for artifact in artifacts:
            grouped.setdefault(artifact.topic or "", []).append(artifact)
        return grouped

    def _topic_document_names(self, user_id: str, topic: str) -> List[str]:
        if not self.data_service or not hasattr(self.data_service, "list_topic_documents"):
            return []
        try:
            return list(self.data_service.list_topic_documents(user_id, topic))
        except Exception:
            return []

    def _topic_document_manifests(self, user_id: str, topic: str) -> List[Dict[str, Any]]:
        if not self.data_service or not hasattr(self.data_service, "get_topic_document_manifests"):
            return []
        try:
            return list(self.data_service.get_topic_document_manifests(user_id, topic))
        except Exception:
            return []

    def _topic_index(self, user_id: str, topic: str) -> Dict[str, Any]:
        try:
            return self.data_service.get_topic_index(user_id, topic)
        except Exception:
            return {}

    def _topic_notes(self, user_id: str, topic: str) -> str:
        try:
            return self.data_service.get_topic_notes(user_id, topic)
        except Exception:
            return ""

    def _question_count_for_document(self, filename: str, questions: List[Dict[str, Any]]) -> int:
        prefix = f"{filename}#"
        return sum(1 for question in questions if str(question.get("id", "")).startswith(prefix))

    def _load_tutor_config(self, user_id: str) -> Dict[str, Any]:
        if not self.data_service or not hasattr(self.data_service, "load_tutor_config"):
            return {}
        try:
            return dict(self.data_service.load_tutor_config(user_id) or {})
        except Exception:
            return {}

    def _student_summary(self, student: StudentModel) -> Dict[str, Any]:
        return {
            "identity": student.identity,
            "goals_and_constraints": student.goals_and_constraints,
            "stated_preferences_about_self": student.stated_preferences_about_self,
            "inferred_profile": self._memory_entries(student.inferred_profile),
            "progress_patterns": self._memory_entries(student.progress_patterns),
            "relationship_memory": self._memory_entries(student.relationship_memory),
            "metadata": student.metadata,
        }

    def _memory_entries(self, entries: List[StudentMemoryEntry], limit: int = 6) -> List[Dict[str, Any]]:
        return [
            {
                "entry_id": entry.entry_id,
                "summary": entry.summary,
                "confidence": entry.confidence,
                "status": entry.status,
            }
            for entry in entries[:limit]
        ]

    def _teacher_summary(self, bootstrap: OrchestratorBootstrapContext) -> Dict[str, Any]:
        return {
            "soul_loaded": bool(bootstrap.teacher_soul),
            "teacher_model_sections": sorted(bootstrap.teacher_model.keys()),
            "identity_defaults": bootstrap.identity_defaults,
            "teaching_defaults": bootstrap.teaching_defaults,
        }

    def _focus_summary(self, focus: CurrentFocus) -> Dict[str, Any]:
        return {
            "kind": focus.kind.value if focus and focus.kind else "none",
            "artifact_id": focus.artifact_id,
            "topic": focus.topic,
            "lesson_id": focus.lesson_id,
            "curriculum_id": focus.curriculum_id,
            "source_message": focus.source_message,
            "updated_at": focus.updated_at,
            "metadata": focus.metadata,
        }

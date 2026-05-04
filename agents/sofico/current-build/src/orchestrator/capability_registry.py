"""Capability registry for Sofi V2.

The registry names what Sofi can do in product terms and maps those abilities to
the existing code paths that already implement them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CapabilitySpec:
    """One user-facing Sofi capability."""

    name: str
    category: str
    purpose: str
    user_intents: List[str] = field(default_factory=list)
    inputs_needed: List[str] = field(default_factory=list)
    reads_from: List[str] = field(default_factory=list)
    writes_to: List[str] = field(default_factory=list)
    existing_code_paths: List[str] = field(default_factory=list)
    can_use_research: bool = False
    creates_artifacts: bool = False
    notes: str = ""


class CapabilityRegistry:
    """Central registry of Sofi's capabilities."""

    def __init__(self):
        self._capabilities: Dict[str, CapabilitySpec] = self._build_registry()

    def list_capabilities(self) -> List[CapabilitySpec]:
        """Return all capability definitions."""
        return list(self._capabilities.values())

    def get(self, name: str) -> Optional[CapabilitySpec]:
        """Fetch one capability by name."""
        return self._capabilities.get(name)

    def summarize(self) -> Dict[str, str]:
        """Return a simple name -> purpose map."""
        return {spec.name: spec.purpose for spec in self.list_capabilities()}

    def _build_registry(self) -> Dict[str, CapabilitySpec]:
        """Define the first real V2 capability set."""
        capabilities = [
            CapabilitySpec(
                name="onboard_user",
                category="setup",
                purpose="Collect the minimum learner setup needed for Sofico to personalize teaching and persist it in the student model.",
                user_intents=[
                    "first-time setup",
                    "new learner introduction",
                    "quick tutor configuration",
                ],
                inputs_needed=["learner answers", "student model shell", "teacher bootstrap defaults"],
                reads_from=[
                    "student model",
                    "teacher bootstrap stack",
                ],
                writes_to=[
                    "student model",
                    "later: readable learner profile view",
                ],
                existing_code_paths=[
                    "src/orchestrator/onboarding_flow.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="This is the first live Sofico onboarding slice. It replaces the old onboarding path for new users.",
            ),
            CapabilitySpec(
                name="converse",
                category="conversation",
                purpose="Handle natural tutoring conversation, clarification, and lightweight chat without forcing a workflow.",
                user_intents=[
                    "greeting or check-in",
                    "open-ended tutoring question",
                    "light clarification",
                    "meta conversation about learning",
                ],
                inputs_needed=["user turn", "bootstrap context", "conversation state", "current focus when available"],
                reads_from=[
                    "SOUL.md",
                    "IDENTITY.md",
                    "TEACHING.md",
                    "student model",
                    "recent conversation state",
                ],
                writes_to=["conversation state", "later: student observations"],
                existing_code_paths=[
                    "src/services/session_response_service.py",
                    "src/slack_bot.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="This is the anti-vending-machine capability. It keeps Sofi conversational when no stronger workflow is needed.",
            ),
            CapabilitySpec(
                name="explain",
                category="teaching",
                purpose="Explain a topic, artifact, or lesson either on demand or as part of a study plan.",
                user_intents=[
                    "explain this topic",
                    "walk me through this",
                    "teach the current lesson",
                    "I don't understand this concept",
                ],
                inputs_needed=["topic or current focus", "student model", "teaching defaults"],
                reads_from=[
                    "topic notes",
                    "current focus",
                    "study plan when active",
                    "student model",
                    "bootstrap teacher stack",
                ],
                writes_to=["explanation session state", "later: reflection observations"],
                existing_code_paths=[
                    "src/handlers/explanation_handler.py",
                    "src/services/session_response_service.py",
                ],
                can_use_research=True,
                creates_artifacts=False,
                notes="One capability, two contexts: explain_on_demand and explain_lesson.",
            ),
            CapabilitySpec(
                name="ingest_material",
                category="materials",
                purpose="Turn uploaded or pasted source material into study notes and review-ready questions/cards.",
                user_intents=[
                    "process this document",
                    "make notes from this file",
                    "turn this into study materials",
                ],
                inputs_needed=["raw text or file", "optional topic hint", "optional user instructions"],
                reads_from=[
                    "uploaded file",
                    "pasted text",
                    "existing learner topics",
                    "config/profile context when available",
                ],
                writes_to=[
                    "study documents",
                    "question index",
                    "topic folders",
                    "later: study artifact registry",
                ],
                existing_code_paths=[
                    "src/handlers/upload_handler.py",
                    "src/services/document_parser_service.py",
                    "src/services/file_extraction_service.py",
                ],
                can_use_research=False,
                creates_artifacts=True,
                notes="This is one pipeline in the current code: extract -> parse -> save notes/questions.",
            ),
            CapabilitySpec(
                name="create_study_artifacts",
                category="materials",
                purpose="Create or update notes, cards, quiz material, and lesson documents from study inputs.",
                user_intents=[
                    "make cards from this",
                    "create notes",
                    "generate review material",
                    "prepare lesson materials",
                ],
                inputs_needed=["source artifact or parsed content", "topic", "teaching context when relevant"],
                reads_from=[
                    "parsed documents",
                    "study plan lessons",
                    "existing notes and question data",
                ],
                writes_to=[
                    "notes",
                    "cards/questions",
                    "quiz-ready materials",
                    "later: study artifact registry",
                ],
                existing_code_paths=[
                    "src/handlers/upload_handler.py",
                    "src/handlers/curriculum_handler.py",
                    "src/services/document_parser_service.py",
                ],
                can_use_research=False,
                creates_artifacts=True,
                notes="This overlaps with ingest_material at first. The registry keeps it visible as a product concept.",
            ),
            CapabilitySpec(
                name="show_artifacts",
                category="materials",
                purpose="Show what notes, question sets, and saved study materials Sofico has created or can use.",
                user_intents=[
                    "what did you create",
                    "show my notes",
                    "what questions did you make",
                    "what have we uploaded",
                    "show the key concepts from this paper",
                ],
                inputs_needed=["current focus or optional topic"],
                reads_from=[
                    "artifact registry",
                    "topic notes",
                    "question index",
                    "current focus",
                ],
                writes_to=[],
                existing_code_paths=[
                    "src/orchestrator/artifact_store.py",
                    "src/services/local_file_service.py",
                    "src/services/gitlab_service.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="Read-only artifact awareness. It should summarize saved materials without inventing new storage.",
            ),
            CapabilitySpec(
                name="list_documents",
                category="materials",
                purpose="List saved documents, optionally scoped to one topic, using the canonical document store rather than only topic notes.",
                user_intents=[
                    "what papers do i have",
                    "show papers in this topic",
                    "list my documents",
                ],
                inputs_needed=["optional topic scope", "document manifests", "current focus when relevant"],
                reads_from=[
                    "canonical document manifests",
                    "topic memberships",
                    "current focus",
                ],
                writes_to=[],
                existing_code_paths=[
                    "src/services/document_library_service.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="This is the library-catalog view: document-first, not topic-notes-first.",
            ),
            CapabilitySpec(
                name="show_document",
                category="materials",
                purpose="Show one saved document's profile, metadata, and readiness state.",
                user_intents=[
                    "show this paper",
                    "what is this document",
                    "show Ward paper",
                ],
                inputs_needed=["document reference or current focus"],
                reads_from=[
                    "canonical document manifest",
                    "document notes/questions readiness",
                    "artifact focus",
                ],
                writes_to=["current focus"],
                existing_code_paths=[
                    "src/services/document_library_service.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="This is the per-document profile card.",
            ),
            CapabilitySpec(
                name="move_document",
                category="materials",
                purpose="Move a saved document from one topic to another while keeping the canonical document identity stable.",
                user_intents=[
                    "move this paper to another topic",
                    "put Ward under consciousness",
                ],
                inputs_needed=["document reference", "destination topic"],
                reads_from=[
                    "canonical document manifest",
                    "topic index",
                    "artifact registry",
                ],
                writes_to=[
                    "canonical manifest",
                    "topic indexes",
                    "artifact registry",
                    "compatibility topic documents",
                ],
                existing_code_paths=[
                    "src/services/document_library_service.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="Move changes the shelf, not the document passport.",
            ),
            CapabilitySpec(
                name="rename_document",
                category="materials",
                purpose="Rename the saved display label for a document without changing its canonical identity.",
                user_intents=[
                    "rename this paper",
                    "call this document something else",
                ],
                inputs_needed=["document reference", "new display title"],
                reads_from=[
                    "canonical document manifest",
                    "artifact registry",
                    "topic indexes",
                ],
                writes_to=[
                    "canonical manifest",
                    "artifact registry",
                    "topic indexes",
                ],
                existing_code_paths=[
                    "src/services/document_library_service.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="Rename changes the library label, not the underlying document id.",
            ),
            CapabilitySpec(
                name="synthesize_topic",
                category="teaching",
                purpose="Find patterns, agreements, tensions, and open questions across multiple saved papers in one topic.",
                user_intents=[
                    "find connections between papers",
                    "compare all papers in this topic",
                    "what themes run across these documents",
                ],
                inputs_needed=["topic scope", "topic corpus"],
                reads_from=[
                    "canonical document manifests",
                    "document notes",
                    "document summaries",
                    "topic corpus",
                ],
                writes_to=["current focus", "later: topic synthesis artifacts"],
                existing_code_paths=[
                    "src/services/topic_corpus_service.py",
                    "src/services/topic_synthesis_service.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="This is the first cross-document reasoning slice inside one saved topic.",
            ),
            CapabilitySpec(
                name="repair_library",
                category="maintenance",
                purpose="Repair topic indexes and remove safe duplicate artifact rows when the saved document library drifts out of sync.",
                user_intents=[
                    "reindex my papers",
                    "repair the library",
                    "clean duplicate artifacts",
                ],
                inputs_needed=["optional topic scope"],
                reads_from=[
                    "canonical document manifests",
                    "topic indexes",
                    "artifact registry",
                ],
                writes_to=[
                    "topic indexes",
                    "artifact registry",
                ],
                existing_code_paths=[
                    "src/services/library_maintenance_service.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="This is the janitor capability: boring, important, and best when it is safe.",
            ),
            CapabilitySpec(
                name="recall_context",
                category="memory",
                purpose="Answer what Sofico and the learner were doing recently using saved focus, session state, and memory summaries.",
                user_intents=[
                    "what were we doing",
                    "where did we leave off",
                    "what was I studying",
                    "what did we do last time",
                    "continue where we left off",
                ],
                inputs_needed=["recent task state", "current focus", "memory.yaml"],
                reads_from=[
                    "recent_task_state.yaml",
                    "memory.yaml",
                    "current focus",
                    "available topics",
                ],
                writes_to=[],
                existing_code_paths=[
                    "src/orchestrator/session_controller.py",
                    "src/services/conversation_memory_service.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="First deterministic memory recall slice. It should not invent past activity.",
            ),
            CapabilitySpec(
                name="plan_study",
                category="planning",
                purpose="Create or update a study plan/curriculum and connect it to lessons.",
                user_intents=[
                    "make me a study plan",
                    "build a curriculum",
                    "update my course",
                    "plan two weeks of study",
                ],
                inputs_needed=["subject", "learner goals", "time/constraints when available"],
                reads_from=[
                    "student model",
                    "profile/preferences",
                    "existing curriculum plan",
                    "topic/artifact context when relevant",
                ],
                writes_to=[
                    "curriculum state",
                    "curriculum plan",
                    "lesson documents",
                ],
                existing_code_paths=[
                    "src/handlers/curriculum_handler.py",
                ],
                can_use_research=True,
                creates_artifacts=True,
                notes="Planning is a tutoring capability. Research is a supporting ability it may call when needed.",
            ),
            CapabilitySpec(
                name="review",
                category="review",
                purpose="Run quizzes and spaced-repetition review using the existing SM-2 system.",
                user_intents=[
                    "quiz me",
                    "test me",
                    "review due questions",
                    "practice this topic",
                ],
                inputs_needed=["topic filter optional", "due questions", "review state"],
                reads_from=[
                    "question index",
                    "due-question scheduling",
                    "topic notes for hint context",
                    "student preferences when relevant",
                ],
                writes_to=[
                    "study session state",
                    "question mastery/scheduling",
                    "session logs",
                ],
                existing_code_paths=[
                    "src/handlers/study_handler.py",
                    "src/services/sm2_service.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="This is the live review engine built around the existing SM-2 scheduler.",
            ),
            CapabilitySpec(
                name="show_progress",
                category="progress",
                purpose="Show current learning progress, due work, weak spots, and mastery summaries.",
                user_intents=[
                    "show my progress",
                    "how am I doing",
                    "what should I review",
                ],
                inputs_needed=["user stats"],
                reads_from=[
                    "question stats",
                    "session counts",
                    "topic mastery data",
                ],
                writes_to=[],
                existing_code_paths=[
                    "src/handlers/progress_handler.py",
                ],
                can_use_research=False,
                creates_artifacts=False,
                notes="This will later connect more tightly to the student model and progress patterns.",
            ),
            CapabilitySpec(
                name="research",
                category="support",
                purpose="Look up current or uncertain information when internal knowledge and saved materials are not enough.",
                user_intents=[
                    "what is the latest on X",
                    "find good resources",
                    "use the web when needed",
                ],
                inputs_needed=["question or topic", "reason research is needed"],
                reads_from=[
                    "current focus",
                    "student model",
                    "teacher stack",
                ],
                writes_to=["later: source references", "later: linked research artifacts"],
                existing_code_paths=[
                    "No dedicated local code path yet; this is a planned orchestrator-supported capability.",
                ],
                can_use_research=True,
                creates_artifacts=False,
                notes="Supporting capability used by explain and plan_study when freshness or uncertainty matters.",
            ),
        ]
        return {capability.name: capability for capability in capabilities}

"""LLM turn interpreter for Sofico's OpenClaw-style agent loop."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import logging
import os
from typing import Any, Dict, Optional

from llm_utils import MODEL_DEFAULT
from .context_engine import SoficoContextPacket

logger = logging.getLogger(__name__)


VALID_CAPABILITIES = {
    "onboard_user",
    "converse",
    "explain",
    "ingest_material",
    "create_study_artifacts",
    "show_artifacts",
    "list_documents",
    "show_document",
    "move_document",
    "rename_document",
    "delete_topic",
    "batch_confirm",
    "synthesize_topic",
    "repair_library",
    "recall_context",
    "plan_study",
    "review",
    "show_progress",
    "research",
}


@dataclass
class TurnDecision:
    """Structured interpretation of one learner turn."""

    capability: str = "converse"
    intent: str = "unknown"
    target: Dict[str, Any] = field(default_factory=dict)
    # Non-empty when the learner issues multiple operations at once.
    # Each item has the same shape as a single-op target plus a "capability" key.
    # When present, capability must be "batch_confirm".
    batch_operations: list = field(default_factory=list)
    continue_active_mode: bool = True
    needs_clarification: bool = False
    clarification_question: str = ""
    confidence: float = 0.0
    debug_note: str = ""
    source: str = "fallback"
    error: str = ""


class TurnInterpreter:
    """Interpret learner intent from a context packet using an LLM."""

    def __init__(self, session_response_service: Any = None, model: Optional[str] = None):
        self.session_response_service = session_response_service
        self.model = model or getattr(session_response_service, "model", MODEL_DEFAULT)
        self.client = getattr(session_response_service, "client", None)

    def enabled(self) -> bool:
        """Return True when an API-backed interpreter can run."""
        return bool(self.client and os.getenv("ANTHROPIC_API_KEY"))

    def interpret(self, packet: SoficoContextPacket, fallback_capability: str = "converse") -> TurnDecision:
        """Return an LLM decision, falling back safely on errors."""
        if not self.enabled():
            return TurnDecision(
                capability=fallback_capability,
                intent="fallback_no_llm",
                confidence=0.0,
                source="fallback",
                error="LLM interpreter is not configured.",
            )

        prompt = self._build_prompt(packet, fallback_capability)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=700,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text for block in response.content if hasattr(block, "text") and block.text
            ).strip()
            decision = self._parse_decision(text, fallback_capability)
            logger.info(
                "interpreter: capability=%s intent=%s hint=%s destination=%s confidence=%.2f",
                decision.capability,
                decision.intent,
                (decision.target or {}).get("document_hint", ""),
                (decision.target or {}).get("destination_topic", ""),
                decision.confidence,
            )
            return decision
        except Exception as exc:
            logger.warning("Turn interpreter failed: %s", exc)
            return TurnDecision(
                capability=fallback_capability,
                intent="fallback_error",
                confidence=0.0,
                source="fallback",
                error=str(exc),
            )

    def to_dict(self, decision: TurnDecision) -> Dict[str, Any]:
        """Serialize a decision for logs and metadata."""
        return asdict(decision)

    def _build_prompt(self, packet: SoficoContextPacket, fallback_capability: str) -> str:
        """Build a compact intent-classification prompt."""
        context = self._compact_packet(packet)
        tutor_name = str((packet.tutor or {}).get("name", "") or "Sofico")
        return f"""
You are {tutor_name}'s turn interpreter.

Your job is to understand what the learner means and select the next capability.
You do not write the final learner-facing answer. You return JSON only.

Important rules:
- Interpret human speech fluidly.
- Use saved documents, topics, current focus, and active workflows.
- Do not invent files or capabilities.
- If the learner is asking to switch tasks, set continue_active_mode=false.
- If the learner is just continuing the current explanation or quiz, keep continue_active_mode=true.
- Use "ingest_material" when the learner is pasting or sharing new content to save. Use "create_study_artifacts" when asking to generate notes or questions from already-saved material.
- Prefer "create_study_artifacts" when the learner wants to refresh or regenerate notes/questions/cards for a document that already exists in saved materials.
- Prefer "research" when the learner asks for external sources, recent work, comparisons with outside papers, or web search.
- Prefer "list_documents" when the learner wants a document inventory, especially papers/documents inside a topic or folder.
- Prefer "show_document" when the learner wants the saved profile or metadata for one exact paper/document.
- Prefer "move_document" when the learner wants to relocate a saved paper to a different topic.
- Prefer "rename_document" when the learner wants to rename the saved label for a paper/document.
- Prefer "delete_topic" when the learner wants to delete or remove a topic folder (not a document).
- Prefer "synthesize_topic" when the learner wants connections, comparisons, or recurring themes across several saved papers in one topic.
- Prefer "repair_library" when the learner explicitly asks to reindex, repair, dedupe, or clean the saved document library.
- Prefer "recall_context" when the learner asks what you know about them, their profile, their learning history, or their persona.
- Use "batch_confirm" when the message contains TWO OR MORE distinct document/folder operations (moves, renames, deletes). Set capability="batch_confirm" and populate batch_operations with each individual operation. Each batch item must have a "capability" key plus the same target fields as a single-op request. batch_operations may ONLY contain "move_document", "rename_document", or "delete_topic" — never "converse", "recall_context", or any other capability.
- For ordinal references like "the second paper" or "that first one", infer the document from its position in the topic's document list in the context packet.
- Set confidence to reflect how certain you are: 0.95+ when the intent is unambiguous, 0.7-0.9 when likely but not explicit, below 0.5 when genuinely unclear (in which case prefer "converse").
- For document_hint: match against the "library" list in the context — it contains every saved paper with its exact title, authors, and the topics it belongs to. Use the title from the library, not the current focus. The focus shows what was recently discussed, not necessarily what the learner is asking to operate on now. If the learner names a paper explicitly, find it in the library by title or author match.

Valid capabilities:
{", ".join(sorted(VALID_CAPABILITIES))}

Fallback deterministic capability: {fallback_capability}

Context packet:
{json.dumps(context, ensure_ascii=False, indent=2)}

Examples:
- "what papers do you have?" -> capability "list_documents", intent "list_saved_documents".
- "what topics do I have?" / "show me my topics" / "list topics" / "full list of topics" -> capability "list_documents", intent "list_topic_folders".
- "who are the authors?" / "show me authors" / "list all authors" -> capability "list_documents", intent "list_authors".
- "what materials do you have?" -> capability "show_artifacts", intent "list_saved_materials".
- "what papers are in consciousness?" -> capability "list_documents", intent "list_documents_in_topic", target.topic "consciousness".
- "show Ward paper" -> capability "show_document", intent "show_saved_document_profile", target.document_hint "Ward".
- "move Ward to electromagnetism" -> capability "move_document", intent "move_saved_document", target.document_hint "Ward", target.destination_topic "electromagnetism".
- "rename this paper to EM field consciousness" -> capability "rename_document", intent "rename_saved_document", target.new_title "EM field consciousness".
- "delete the consciousness folder" -> capability "delete_topic", intent "delete_topic_folder", target.topic "consciousness".
- "move Ward to electromagnetism / delete consciousness folder / rename Nagel to bat paper" -> capability "batch_confirm", intent "batch_document_operations", batch_operations [{{"capability":"move_document","document_hint":"Ward","destination_topic":"electromagnetism"}},{{"capability":"delete_topic","topic":"consciousness"}},{{"capability":"rename_document","document_hint":"Nagel","new_title":"bat paper"}}].
- "quiz me on my consciousness papers" -> capability "review", intent "start_topic_corpus_quiz", target.topic "consciousness".
- "find connections between all papers in consciousness" -> capability "synthesize_topic", intent "synthesize_topic_connections", target.topic "consciousness".
- "reindex my consciousness library" -> capability "repair_library", intent "repair_topic_library", target.topic "consciousness".
- "look into Ward paper and see what he says about my question" -> capability "explain", intent "answer_from_saved_document", target.document_hint "Ward".
- "can you explain how electromagnetic fields give rise to valenced experience?" when a matching saved document exists -> capability "explain", intent "answer_from_saved_document".
- "quiz me on Ward" -> capability "review", intent "start_quiz", target.document_hint "Ward".
- "make notes for the Ward paper" -> capability "create_study_artifacts", intent "create_notes_from_existing", target.document_hint "Ward".
- "regenerate questions for this paper" -> capability "create_study_artifacts", intent "refresh_questions_from_existing".
- "find recent papers that challenge Ward" -> capability "research", intent "research_against_saved_document", target.document_hint "Ward".
- "make notes for the second paper" -> capability "create_study_artifacts", intent "create_notes_from_existing", target.document_hint inferred from position in document list.
- "here is an article I want to study: [text]" -> capability "ingest_material", intent "save_new_material".
- "what were we working on?" -> capability "recall_context", intent "recall_recent_activity".
- "what do you know about me?" -> capability "recall_context", intent "user_self_inquiry".
- "what do you remember about me?" -> capability "recall_context", intent "user_self_inquiry".
- "who am i" -> capability "recall_context", intent "user_self_inquiry".
- "tell me about my learning profile" -> capability "recall_context", intent "user_self_inquiry".
- "what is my persona / about my persona" -> capability "recall_context", intent "user_self_inquiry".
- "how am I doing?" -> capability "show_progress", intent "show_learning_progress".
- "make me a study plan" -> capability "plan_study", intent "create_study_plan".
- "notes please" or "show me the notes" when a paper is in focus -> capability "explain", intent "show_saved_notes".
- "tell me more about that" -> capability "converse", intent "continue_discussion".
- "find me papers on consciousness" -> capability "research", intent "find_external_sources".

Return exactly this JSON shape:
{{
  "capability": "one valid capability",
  "intent": "short_snake_case_intent",
  "target": {{
    "topic": "",
    "artifact_hint": "",
    "document_hint": "",
    "question_category": "",
    "destination_topic": "",
    "new_title": ""
  }},
  "batch_operations": [],
  "continue_active_mode": true,
  "needs_clarification": false,
  "clarification_question": "",
  "confidence": 0.95,
  "debug_note": "brief private reason"
}}

When capability is "batch_confirm", batch_operations must contain each individual operation like:
[
  {{"capability": "move_document", "document_hint": "Ward", "destination_topic": "electromagnetism"}},
  {{"capability": "delete_topic", "topic": "old-folder"}},
  {{"capability": "rename_document", "document_hint": "Nagel", "new_title": "bat paper"}}
]
""".strip()

    def _compact_packet(self, packet: SoficoContextPacket) -> Dict[str, Any]:
        """Keep the interpreter context small but document-aware."""
        # Flat library: every saved paper with its exact title, authors, and the
        # full list of topics it belongs to. Authoritative source for the LLM's
        # document_hint — NOT current focus, NOT recent message text.
        library_by_key: Dict[str, Dict[str, Any]] = {}
        for topic in packet.topics:
            for doc in topic.documents:
                if doc.artifact_type != "uploaded_source":
                    continue
                key = doc.doc_id or doc.source_path
                if not key:
                    continue
                entry = library_by_key.get(key)
                if entry is None:
                    library_by_key[key] = {
                        "title": doc.title,
                        "authors": doc.authors,
                        "year": doc.year,
                        "topics": [topic.name],
                        "doc_id": doc.doc_id,
                    }
                elif topic.name not in entry["topics"]:
                    entry["topics"].append(topic.name)
        library = list(library_by_key.values())

        # Focus: keep artifact_id and topic for routing — strip document_title
        # to avoid anchoring the LLM to the last-touched paper across turns.
        focus = dict(packet.focus or {})
        focus.pop("metadata", None)

        return {
            "turn": packet.turn,
            "tutor": {"name": str((packet.tutor or {}).get("name", "") or "Sofico")},
            "focus": focus,
            "active_workflows": asdict(packet.active_workflows),
            "learner": {
                "identity": packet.learner.get("identity", {}),
                "goals_and_constraints": packet.learner.get("goals_and_constraints", {}),
                "preferences": packet.learner.get("stated_preferences_about_self", {}),
            },
            "learner_brief": {
                "learner_name": packet.learner_brief.get("learner_name", ""),
                "study_goals": list(packet.learner_brief.get("study_goals", []) or [])[:4],
                "preferred_subjects": list(packet.learner_brief.get("preferred_subjects", []) or [])[:5],
                "learning_preferences": list(packet.learner_brief.get("learning_preferences", []) or [])[:5],
                "inferred_profile": list(packet.learner_brief.get("inferred_profile", []) or [])[:5],
                "progress_patterns": list(packet.learner_brief.get("progress_patterns", []) or [])[:5],
                "relationship_memory": list(packet.learner_brief.get("relationship_memory", []) or [])[:4],
                "psychological_profile": {
                    "learning_style": (packet.learner_brief.get("psychological_profile", {}) or {}).get("learning_style", ""),
                    "strengths": list(((packet.learner_brief.get("psychological_profile", {}) or {}).get("strengths", []) or [])[:4]),
                    "growth_areas": list(((packet.learner_brief.get("psychological_profile", {}) or {}).get("growth_areas", []) or [])[:4]),
                    "resistance_patterns": list(((packet.learner_brief.get("psychological_profile", {}) or {}).get("resistance_patterns", []) or [])[:3]),
                    "best_strategies": list(((packet.learner_brief.get("psychological_profile", {}) or {}).get("best_strategies", []) or [])[:3]),
                },
                "recent_sessions": list(packet.learner_brief.get("recent_sessions", []) or [])[:2],
            },
            "recent_messages": packet.recent_messages[-6:],
            "library": library,
            "topics": [
                {
                    "name": topic.name,
                    "question_count": topic.question_count,
                    "notes_available": topic.notes_available,
                    "documents": [
                        {
                            "doc_id": doc.doc_id,
                            "title": doc.title,
                            "source_path": doc.source_path,
                            "artifact_type": doc.artifact_type,
                            "doc_type": doc.doc_type,
                            "authors": doc.authors,
                            "year": doc.year,
                            "question_count": doc.question_count,
                            "notes_ready": doc.notes_ready,
                            "quiz_ready": doc.quiz_ready,
                        }
                        for doc in topic.documents[:12]
                    ],
                }
                for topic in packet.topics[:12]
            ],
            "capabilities": packet.capabilities,
        }

    def _parse_decision(self, text: str, fallback_capability: str) -> TurnDecision:
        """Parse and validate the interpreter JSON."""
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError("No JSON object found.")
            data = json.loads(text[start : end + 1])
        except Exception as exc:
            return TurnDecision(
                capability=fallback_capability,
                intent="fallback_parse_error",
                confidence=0.0,
                source="fallback",
                error=str(exc),
            )

        capability = str(data.get("capability") or fallback_capability)
        if capability not in VALID_CAPABILITIES:
            capability = fallback_capability

        try:
            confidence = float(data.get("confidence", 0.0))
        except Exception:
            confidence = 0.0

        raw_batch = data.get("batch_operations")
        batch_operations = list(raw_batch) if isinstance(raw_batch, list) else []

        return TurnDecision(
            capability=capability,
            intent=str(data.get("intent") or "unknown"),
            target=dict(data.get("target") or {}),
            batch_operations=batch_operations,
            continue_active_mode=bool(data.get("continue_active_mode", True)),
            needs_clarification=bool(data.get("needs_clarification", False)),
            clarification_question=str(data.get("clarification_question") or ""),
            confidence=max(0.0, min(1.0, confidence)),
            debug_note=str(data.get("debug_note") or ""),
            source="llm",
        )

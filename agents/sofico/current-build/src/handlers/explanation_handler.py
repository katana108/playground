"""
Explanation Handler
Natural conversation walkthrough of study notes.
Sofi has the full content and follows the learner's lead — no chunks, no navigation commands.
"""

import json
import logging
import re
import copy
import threading
from datetime import date
from typing import Dict, Any, Optional

from llm_utils import llm_text

logger = logging.getLogger(__name__)


class ExplanationHandler:
    """
    Manages explanation sessions.

    Flow:
    1. User says "explain X" → start(user, topic, say)
    2. Sofi introduces the topic and begins naturally
    3. Learner drives: asks questions, says "go deeper", "move on", etc.
    4. Sofi signals "end" when the topic is fully covered or learner wraps up
    5. handle() returns an action string ("quiz"|"customize"|None) to caller

    Session state: {topic, full_content, history, started_at}
    """

    def __init__(self, data_service, session_response_service, profile_service):
        self.data_service = data_service
        self.response_service = session_response_service
        self.profile_service = profile_service
        self.client = session_response_service.client
        self.model = session_response_service.model
        self.active_explanations: Dict[str, Dict[str, Any]] = {}
        self.last_completed_explanations: Dict[str, Dict[str, Any]] = {}
        self._explanations_lock = threading.Lock()

    def is_active(self, user_id: str) -> bool:
        with self._explanations_lock:
            return user_id in self.active_explanations

    def cancel(self, user_id: str):
        """Drop an explanation session without saving notes."""
        with self._explanations_lock:
            self.active_explanations.pop(user_id, None)

    def take_last_completed_explanation(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return and clear the most recent completed explanation snapshot."""
        session = self.last_completed_explanations.pop(user_id, None)
        return copy.deepcopy(session) if session else None

    def start(
        self,
        user_id: str,
        topic: str,
        say,
        preference_overrides: Optional[Dict[str, Any]] = None,
        learner_brief: Optional[Dict[str, Any]] = None,
        from_curriculum: bool = False,
    ):
        """Start an explanation session for a topic."""
        available = self.data_service.get_available_topics(user_id)
        resolved = self.response_service.resolve_topic(topic, available)
        if not resolved:
            topics_str = ", ".join(available) if available else "none found"
            say(f"I couldn't find notes for *{topic}*.\nAvailable topics: {topics_str}")
            return

        content = self.data_service.get_topic_notes(user_id, resolved)
        if not content or len(content.strip()) < 50:
            say(f"The notes for *{resolved}* are too thin to explain. Try uploading more material first.")
            return

        notes_only = content.strip()

        profile = self.profile_service.load_profile(user_id)

        self.active_explanations[user_id] = {
            "topic": resolved,
            "full_content": notes_only,
            "history": [],
            "started_at": date.today().isoformat(),
            "profile": profile,
            "learner_brief": copy.deepcopy(learner_brief or {}),
            "preference_overrides": preference_overrides or {},
            "from_curriculum": from_curriculum,
            "scope_type": "topic",
            "scope_label": resolved,
            "doc_name": "",
        }

        opening = self._get_explanation_response(
            user_id,
            user_message=f"Please introduce and begin explaining {resolved}.",
            is_opening=True,
        )
        say(opening["message"])
        self.active_explanations[user_id]["history"].append(
            {"role": "assistant", "content": opening["message"]}
        )

    def start_document(
        self,
        user_id: str,
        *,
        artifact_title: str,
        topic: str,
        doc_name: str,
        notes_only: str,
        say,
        initial_user_message: str = "",
        preference_overrides: Optional[Dict[str, Any]] = None,
        learner_brief: Optional[Dict[str, Any]] = None,
    ):
        """Start an explanation session grounded in one exact saved document."""
        if not notes_only or len(notes_only.strip()) < 50:
            say(f"The notes for *{artifact_title}* are too thin to explain yet.")
            return

        profile = self.profile_service.load_profile(user_id)

        self.active_explanations[user_id] = {
            "topic": topic,
            "full_content": notes_only.strip(),
            "history": [],
            "started_at": date.today().isoformat(),
            "profile": profile,
            "learner_brief": copy.deepcopy(learner_brief or {}),
            "preference_overrides": preference_overrides or {},
            "from_curriculum": False,
            "scope_type": "document",
            "scope_label": artifact_title,
            "doc_name": doc_name,
        }

        if initial_user_message.strip():
            self.active_explanations[user_id]["history"].append(
                {"role": "user", "content": initial_user_message}
            )
            opening = self._get_explanation_response(
                user_id,
                user_message=initial_user_message,
                is_opening=False,
            )
        else:
            opening = self._get_explanation_response(
                user_id,
                user_message=f"Please introduce and begin explaining {artifact_title}.",
                is_opening=True,
            )

        say(opening["message"])
        self.active_explanations[user_id]["history"].append(
            {"role": "assistant", "content": opening["message"]}
        )

    def activate_document_session(
        self,
        user_id: str,
        *,
        artifact_title: str,
        topic: str,
        doc_name: str,
        notes_only: str,
        history: Optional[list[Dict[str, Any]]] = None,
        preference_overrides: Optional[Dict[str, Any]] = None,
        learner_brief: Optional[Dict[str, Any]] = None,
    ):
        """Seed an active document explanation session without sending a fresh opening."""
        if not notes_only or len(notes_only.strip()) < 50:
            return

        profile = self.profile_service.load_profile(user_id)
        self.active_explanations[user_id] = {
            "topic": topic,
            "full_content": notes_only.strip(),
            "history": copy.deepcopy(history or []),
            "started_at": date.today().isoformat(),
            "profile": profile,
            "learner_brief": copy.deepcopy(learner_brief or {}),
            "preference_overrides": preference_overrides or {},
            "from_curriculum": False,
            "scope_type": "document",
            "scope_label": artifact_title,
            "doc_name": doc_name,
        }

    def handle(
        self,
        user_id: str,
        message: str,
        say,
        preference_overrides: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Handle a user message during an explanation session.
        Returns action string ("quiz"|"customize"|None) when session ends, else None.
        """
        session = self.active_explanations.get(user_id)
        if not session:
            return None

        session["preference_overrides"] = preference_overrides or {}

        session["history"].append({"role": "user", "content": message})

        result = self._get_explanation_response(user_id, user_message=message)
        say(result["message"])
        session["history"].append({"role": "assistant", "content": result["message"]})

        action = result.get("action")

        if action == "end":
            topic = session["topic"]
            scope_type = session.get("scope_type", "topic")
            scope_label = session.get("scope_label", topic)
            doc_name = session.get("doc_name", "")
            self.last_completed_explanations[user_id] = copy.deepcopy(session)
            self._save_notes(user_id, say, include_quiz_prompt=not session.get("from_curriculum", False))
            del self.active_explanations[user_id]
            return {"action": "end", "topic": topic, "scope_type": scope_type, "scope_label": scope_label, "doc_name": doc_name}

        if action in ("quiz", "customize"):
            topic = session["topic"]
            scope_type = session.get("scope_type", "topic")
            scope_label = session.get("scope_label", topic)
            doc_name = session.get("doc_name", "")
            self.last_completed_explanations[user_id] = copy.deepcopy(session)
            del self.active_explanations[user_id]
            return {"action": action, "topic": topic, "scope_type": scope_type, "scope_label": scope_label, "doc_name": doc_name}

        return None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_explanation_response(
        self,
        user_id: str,
        user_message: str,
        is_opening: bool = False,
    ) -> dict:
        """
        Single LLM call. Returns {"message": str, "action": null|"end"|"quiz"|"customize"}.
        """
        session = self.active_explanations[user_id]
        profile = session["profile"]
        learner_brief = session.get("learner_brief", {}) or {}
        topic = session["topic"]
        scope_type = session.get("scope_type", "topic")
        scope_label = session.get("scope_label", topic)
        full_content = session["full_content"]
        history = session["history"]
        preference_overrides = session.get("preference_overrides") or {}

        style_brief = learner_brief.get("style", {}) or {}
        tutor_name = style_brief.get("tutor_name") or "Sofico"
        archetype = style_brief.get("archetype") or profile.get("character", {}).get("archetype", "sophia")
        persona_description = style_brief.get("persona_description")
        if persona_description is None:
            persona_description = profile.get("character", {}).get("persona_description")
        name = learner_brief.get("learner_name") or profile.get("metadata", {}).get("learner_name", "")
        motivation = style_brief.get("motivation") or profile.get("motivations", {}).get("primary", "curiosity")
        style = (
            (style_brief.get("explanation_preferences", {}) or {}).get("style")
            or profile.get("explanation_preferences", {}).get("style", "narrative")
        )
        communication = {
            **profile.get("communication", {}),
            **(style_brief.get("communication", {}) or {}),
            **preference_overrides.get("communication", {}),
        }
        interaction_preferences = {
            **profile.get("interaction_preferences", {}),
            **(style_brief.get("interaction_preferences", {}) or {}),
            **preference_overrides.get("interaction_preferences", {}),
        }
        metaphors = communication.get("metaphor_preferences", {}).get("preferred", [])
        verbosity = communication.get("verbosity", "concise")
        theatricality = communication.get("theatricality", "subtle")
        humor_style = communication.get("humor_style", "light")
        proactivity = interaction_preferences.get("proactivity", "medium")

        if persona_description:
            voice_block = persona_description
        else:
            from config.personality import get_archetype_voice
            voice_block = get_archetype_voice(archetype)

        motivation_hints = {
            "curiosity": "Weave in surprising angles and unexpected connections naturally.",
            "achievement": "Frame ideas as building on each other — make progress feel tangible.",
            "play": "Keep the energy light; make ideas feel like interesting puzzles.",
            "social": "Connect ideas to real-world impact or how you'd explain this to someone else.",
        }

        style_hints = {
            "narrative": "Explain as a flowing narrative, ideas connecting naturally.",
            "logical-steps": "Step by step, each building on the previous.",
            "examples-first": "Lead with a concrete example, then the underlying principle.",
        }

        metaphor_hint = (
            f"When helpful, use metaphors drawn from: {', '.join(metaphors)}." if metaphors else ""
        )
        verbosity_hint = {
            "concise": "Keep replies tight — usually 2-4 sentences unless the learner asks for more.",
            "balanced": "Keep replies moderately detailed and focused.",
            "chatty": "You may be more expansive and conversational when it helps.",
        }.get(verbosity, "Keep replies tight — usually 2-4 sentences unless the learner asks for more.")
        theatricality_hint = {
            "subtle": "Keep the persona grounded and natural rather than dramatic.",
            "expressive": "Let the persona color the response clearly, but keep it sincere and readable.",
            "vivid": "A more stylized persona voice is welcome, but clarity still comes first.",
        }.get(theatricality, "Keep the persona grounded and natural rather than dramatic.")
        humor_hint = {
            "none": "Do not joke unless the learner strongly invites it.",
            "light": "Light wit is fine when natural, but never at the expense of clarity.",
            "playful": "A playful touch is welcome when it supports learning.",
        }.get(humor_style, "Light wit is fine when natural, but never at the expense of clarity.")
        proactivity_hint = {
            "low": "Be restrained. Follow the learner's lead closely and avoid steering unless asked.",
            "medium": "Offer gentle next-step suggestions when useful, but keep the learner in the lead.",
            "high": "Be proactively helpful about where to go next, while still sounding collaborative.",
        }.get(proactivity, "Offer gentle next-step suggestions when useful, but keep the learner in the lead.")

        opening_note = (
            "This is the opening message — introduce the topic naturally and begin explaining. "
            "Don't wait to be asked, just start." if is_opening else ""
        )

        history_block = "\n".join(
            f"{tutor_name if m['role'] == 'assistant' else 'Learner'}: {m['content'][:300]}"
            for m in history[-8:]
        ) or "(conversation just started)"
        learner_brief_block = self._format_learner_brief(learner_brief)

        system_prompt = f"""{voice_block}

You are walking {name or 'a learner'} through their study notes on *{scope_label}*.
You have the full notes as context. You don't narrate sections sequentially — you follow the learner's lead.
The learner can ask questions, go deeper, change direction, or wrap up whenever they want.
The study scope is: {scope_type}. The topic folder is: {topic}.

{style_hints.get(style, '')}
{metaphor_hint}
{verbosity_hint}
{theatricality_hint}
{humor_hint}
{proactivity_hint}
{motivation_hints.get(motivation, '')}
{opening_note}

Guidelines:
- Respond naturally — no "Say 'next' to continue" or section numbers
- If the learner asks something not in the notes, answer from your knowledge
- When the learner seems done, has asked to finish, or you've covered everything naturally, signal end
- Never use theatrical stage directions (*settles*, *pauses*, *leans forward*, etc.)
- Keep each response aligned with the learner's preferred verbosity unless they ask for more depth

## Learner Brief
{learner_brief_block}

## Study Notes
{full_content[:4000]}

## Conversation so far
{history_block}

## Response Format
End every message with this JSON on its own line:
{{"message": "your full response", "action": null}}

action options:
- null: conversation continues
- "end": topic fully covered or learner is done (save notes and close session)
- "quiz": learner explicitly wants to quiz themselves on this topic
- "customize": learner wants to update their learning preferences"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=600,
                messages=[{"role": "user", "content": system_prompt}],
            )
            text = llm_text(response)
            return self._parse_response(text)
        except Exception as e:
            logger.error(f"Error in explanation LLM call for {user_id}: {e}")
            return {"message": "I'm having a moment — could you repeat that?", "action": None}

    def _parse_response(self, text: str) -> dict:
        """Extract JSON signal. Uses text before the marker if JSON is unparseable."""
        json_start = text.rfind('{"message":')
        if json_start == -1:
            return {"message": text, "action": None}

        display_text = text[:json_start].strip()
        json_str = text[json_start:]

        try:
            data = json.loads(json_str)
            return {
                "message": data.get("message") or display_text,
                "action": data.get("action"),
            }
        except json.JSONDecodeError:
            return {"message": display_text or text, "action": None}

    def _format_learner_brief(self, learner_brief: Dict[str, Any]) -> str:
        """Render compact learner context for explanation prompts."""
        if not learner_brief:
            return "No learner brief available yet."

        parts = []
        if learner_brief.get("study_goals"):
            parts.append("- study_goals: " + "; ".join((learner_brief.get("study_goals") or [])[:4]))
        if learner_brief.get("learning_preferences"):
            parts.append("- learning_preferences: " + "; ".join((learner_brief.get("learning_preferences") or [])[:5]))
        if learner_brief.get("inferred_profile"):
            parts.append("- inferred_profile: " + "; ".join((learner_brief.get("inferred_profile") or [])[:5]))
        if learner_brief.get("progress_patterns"):
            parts.append("- progress_patterns: " + "; ".join((learner_brief.get("progress_patterns") or [])[:5]))

        psych = learner_brief.get("psychological_profile", {}) or {}
        if psych.get("strengths"):
            parts.append("- strengths: " + "; ".join((psych.get("strengths") or [])[:4]))
        if psych.get("growth_areas"):
            parts.append("- growth_areas: " + "; ".join((psych.get("growth_areas") or [])[:4]))
        if psych.get("best_strategies"):
            parts.append("- best_strategies: " + "; ".join((psych.get("best_strategies") or [])[:3]))

        recent = learner_brief.get("recent_sessions", []) or []
        if recent:
            rendered = []
            for session in recent[:2]:
                summary = str(session.get("summary", "") or "").strip()
                if summary:
                    rendered.append(summary)
            if rendered:
                parts.append("- recent_sessions: " + " | ".join(rendered))

        return "\n".join(parts) if parts else "No learner brief available yet."

    def _save_notes(self, user_id: str, say, include_quiz_prompt: bool = True):
        """Generate and save a study guide from the explanation session."""
        session = self.active_explanations.get(user_id)
        if not session:
            return

        topic = session["topic"]
        scope_label = session.get("scope_label", topic)
        profile = session["profile"]
        name = profile.get("metadata", {}).get("learner_name", "Learner")

        try:
            notes_prompt = (
                f"You just walked {name} through {scope_label}. "
                f"Write concise study notes (200-300 words) based on the content below:\n"
                f"- Capture the key concepts clearly with headers\n"
                f"- Use clean markdown formatting\n"
                f"- Useful for quick review\n\n"
                f"Content:\n{session['full_content'][:3000]}"
            )
            response = self.client.messages.create(
                model=self.model,
                max_tokens=600,
                messages=[{"role": "user", "content": notes_prompt}],
            )
            notes = llm_text(response)

            today = date.today().isoformat()
            try:
                self.data_service.save_study_guide(user_id, f"explanation-{topic}-{today}", notes)
                say(f"*Study notes saved!* Here's what I captured:\n\n{notes}")
            except Exception as e:
                logger.warning(f"Could not save explanation notes: {e}")
                say(f"*Here are your study notes:*\n\n{notes}\n\n_(Couldn't save — please copy these.)_")

        except Exception as e:
            logger.error(f"Error generating explanation notes: {e}")

        if include_quiz_prompt:
            say(f"\n---\nWant to quiz yourself on *{scope_label}*? Say `quiz me on this`.")

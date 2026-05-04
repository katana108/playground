"""Lightweight onboarding workflow for the first live Sofico slice.

This is intentionally narrow. It asks only the minimum structured questions
needed to populate the existing student model for a new learner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Dict, Optional

import yaml

from .student_model import StudentModel, StudentModelStore, utc_now_iso


ONBOARDING_FLOW_VERSION = "sofico-v2-essential-2026-04-22"


@dataclass
class OnboardingSession:
    """In-progress onboarding state for one learner."""

    step_index: int = 0
    draft: Dict[str, Any] = field(default_factory=dict)
    flow_version: str = ONBOARDING_FLOW_VERSION


class SoficoOnboardingFlow:
    """Guide a new learner through a short structured onboarding workflow."""

    def __init__(
        self,
        student_model_store: Optional[StudentModelStore] = None,
        profile_service: Optional[Any] = None,
    ):
        self.student_model_store = student_model_store or StudentModelStore()
        self.profile_service = profile_service
        self._sessions: Dict[str, OnboardingSession] = {}

    # ── session persistence ──────────────────────────────────────────────────

    def _session_path(self, user_id: str) -> Path:
        return self.student_model_store.get_path(user_id).parent / "onboarding_state.yaml"

    def _load_session(self, user_id: str) -> Optional[OnboardingSession]:
        """Load a persisted mid-onboarding session from disk if one exists."""
        path = self._session_path(user_id)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if "step_index" not in data or "draft" not in data:
                return None
            if data.get("flow_version") != ONBOARDING_FLOW_VERSION:
                path.unlink(missing_ok=True)
                return None
            return OnboardingSession(
                step_index=int(data.get("step_index", 0)),
                draft=dict(data.get("draft", {})),
                flow_version=ONBOARDING_FLOW_VERSION,
            )
        except Exception:
            return None

    def _save_session(self, user_id: str, session: OnboardingSession) -> None:
        path = self._session_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(
                {
                    "flow_version": ONBOARDING_FLOW_VERSION,
                    "step_index": session.step_index,
                    "draft": session.draft,
                },
                fh,
            )

    def _clear_session(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)
        path = self._session_path(user_id)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

    # ── public interface ─────────────────────────────────────────────────────

    def clear(self, user_id: str) -> None:
        """Clear any in-progress onboarding state for a learner."""
        self._clear_session(user_id)

    def is_active(self, user_id: str) -> bool:
        """Return True when the learner is mid-onboarding (memory or disk)."""
        if user_id in self._sessions:
            return True
        session = self._load_session(user_id)
        if session is not None:
            self._sessions[user_id] = session
            return True
        return False

    def needs_onboarding(self, model: StudentModel) -> bool:
        """Return True when the learner model lacks the first working slice essentials."""
        metadata = model.metadata or {}
        if metadata.get("requires_v2_onboarding"):
            return True
        if not metadata.get("onboarding_completed_at"):
            return True

        name = (model.identity or {}).get("learner_name", "").strip()
        goals = (model.goals_and_constraints or {}).get("study_goals", []) or []
        subjects = (model.goals_and_constraints or {}).get("preferred_subjects", []) or []
        preferences = (model.stated_preferences_about_self or {}).get("learning_preferences", []) or []
        return not (name and (goals or subjects) and preferences)

    def start(self, user_id: str) -> str:
        """Start onboarding and return the first prompt."""
        model = self.student_model_store.load(user_id)
        if not self.needs_onboarding(model):
            self._clear_session(user_id)
            name = (
                (model.identity or {}).get("preferred_form_of_address")
                or (model.identity or {}).get("learner_name")
                or "there"
            )
            return f"Welcome back, {name}. I already have your learner profile loaded."

        session = OnboardingSession()
        self._sessions[user_id] = session
        self._save_session(user_id, session)
        return (
            "I'm Sofico. Before we start, I want a quick setup so I can teach you coherently over time, not like a goldfish with a laptop.\n\n"
            + self._prompt_for_step(0, {})
        )

    def handle(self, user_id: str, message: str) -> Dict[str, Any]:
        """Consume one learner answer and return the next onboarding state."""
        if user_id not in self._sessions:
            session = self._load_session(user_id)
            if session is None:
                session = OnboardingSession()
            self._sessions[user_id] = session

        session = self._sessions[user_id]
        cleaned = message.strip()
        normalized = cleaned.lower()

        if normalized in {"restart", "start over"}:
            new_session = OnboardingSession()
            self._sessions[user_id] = new_session
            self._save_session(user_id, new_session)
            return {
                "completed": False,
                "reply": "Okay. We'll restart the setup.\n\n" + self._prompt_for_step(0, {}),
            }

        if normalized in {"cancel", "stop"}:
            self._clear_session(user_id)
            return {
                "completed": False,
                "reply": "Okay. I stopped setup. When you're ready, say hi and I'll start again.",
            }

        validation_error = self._validation_error(session.step_index, cleaned)
        if validation_error:
            return {
                "completed": False,
                "reply": validation_error + "\n\n" + self._prompt_for_step(session.step_index, session.draft),
            }

        if session.step_index == 0:
            name = self._extract_name(cleaned)
            session.draft["learner_name"] = name
            session.draft["preferred_form_of_address"] = name
        elif session.step_index == 1:
            session.draft["study_goal"] = cleaned
            session.draft["preferred_subject"] = cleaned
        elif session.step_index == 2:
            session.draft["topic_proficiency"] = cleaned
        elif session.step_index == 3:
            session.draft["learning_preference"] = cleaned
            model = self._persist(user_id, session.draft)
            self._clear_session(user_id)
            return {
                "completed": True,
                "reply": (
                    f"Good. I've saved your setup, {model.identity.get('preferred_form_of_address') or model.identity.get('learner_name') or 'there'}.\n\n"
                    "Now upload a file or paste text, and I'll turn it into notes and study questions."
                ),
                "student_model": model,
            }

        session.step_index += 1
        self._save_session(user_id, session)
        return {
            "completed": False,
            "reply": self._prompt_for_step(session.step_index, session.draft),
        }

    def _persist(self, user_id: str, draft: Dict[str, Any]) -> StudentModel:
        """Write the onboarding answers into the existing student model."""
        model = self.student_model_store.load(user_id)
        subject = draft.get("preferred_subject", "").strip()

        model.identity["learner_name"] = draft.get("learner_name", "").strip()
        model.identity["preferred_form_of_address"] = draft.get("preferred_form_of_address", "").strip()

        if subject:
            topic_proficiency = dict(model.identity.get("topic_proficiency", {}) or {})
            topic_proficiency[subject] = draft.get("topic_proficiency", "").strip()
            model.identity["topic_proficiency"] = topic_proficiency

        goals = model.goals_and_constraints
        study_goal = draft.get("study_goal", "").strip()
        if study_goal:
            goals["study_goals"] = [study_goal]
            goals["current_priorities"] = [study_goal]
        if subject:
            goals["preferred_subjects"] = [subject]

        preferences = model.stated_preferences_about_self
        learning_preference = draft.get("learning_preference", "").strip()
        if learning_preference:
            preferences["direct_statements"] = [learning_preference]
            preferences["learning_preferences"] = [learning_preference]

        completed_at = utc_now_iso()
        model.metadata["onboarding_completed_at"] = completed_at
        model.metadata["requires_v2_onboarding"] = False
        model.metadata["legacy_profile_needs_review"] = False
        self.student_model_store.save(user_id, model)
        self._sync_legacy_profile_name(user_id, model, completed_at)
        return self.student_model_store.load(user_id)

    def _sync_legacy_profile_name(self, user_id: str, model: StudentModel, completed_at: str) -> None:
        """Keep old profile readers from using a stale learner name."""
        name = (
            (model.identity or {}).get("preferred_form_of_address")
            or (model.identity or {}).get("learner_name")
            or ""
        ).strip()
        if not name:
            return

        profile_path = self.student_model_store.get_path(user_id).parent / "profile.yaml"
        try:
            if profile_path.exists():
                with profile_path.open("r", encoding="utf-8") as fh:
                    profile = yaml.safe_load(fh) or {}
            else:
                profile = {}
            metadata = profile.setdefault("metadata", {})
            metadata["learner_name"] = name
            metadata["last_updated"] = completed_at
            metadata["v2_onboarding_synced_at"] = completed_at
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            with profile_path.open("w", encoding="utf-8") as fh:
                yaml.safe_dump(profile, fh, sort_keys=False, allow_unicode=True)
            if self.profile_service and hasattr(self.profile_service, "invalidate_cache"):
                self.profile_service.invalidate_cache(user_id)
        except Exception:
            return

    def _prompt_for_step(self, step_index: int, draft: Dict[str, Any]) -> str:
        """Return the prompt for one onboarding step."""
        if step_index == 0:
            return "What should I call you?"
        if step_index == 1:
            name = draft.get("preferred_form_of_address") or draft.get("learner_name") or "you"
            return f"Good to meet you, {name}. What do you want to study right now? You can answer with the subject or the goal."
        if step_index == 2:
            subject = draft.get("preferred_subject", "that subject")
            return f"Good. Where would you place yourself in {subject} right now? Beginner, intermediate, advanced, or your own words."
        return (
            "That helps. How should I teach you? You can answer in your own words, or say things like "
            "`examples first`, `big picture first`, `step by step`, `direct feedback`, or `concise`."
        )

    def _validation_error(self, step_index: int, message: str) -> str:
        """Reject obvious non-answers so onboarding cannot corrupt the student model."""
        text = message.strip()
        lowered = text.lower()
        if not text:
            return "I need an answer before I can save this part."

        if lowered in {"hi", "hello", "hey", "yo", "hiya", "good morning", "good afternoon", "good evening"}:
            return "That was a greeting, not setup information."

        if step_index == 0:
            if self._looks_like_question(text):
                return "I do not have a reliable name answer from that."
            extracted = self._extract_name(text)
            if len(extracted) < 2:
                return "That name is too short for me to save confidently."
            if len(extracted.split()) > 4 or len(extracted) > 80:
                return "That looks too long to be a name."
            if any(word in lowered.split() for word in {"study", "learn", "explain", "quiz", "plan"}):
                return "That sounds like a learning request, not your name."
            return ""

        if step_index in {1, 2, 3} and self._looks_like_question(text):
            return "That sounds like a question rather than an answer to this setup step."

        return ""

    def _looks_like_question(self, message: str) -> bool:
        """Return True for obvious questions that should not be saved as setup fields."""
        lowered = message.strip().lower()
        if "?" in lowered:
            return True
        question_starters = (
            "what ",
            "who ",
            "why ",
            "how ",
            "when ",
            "where ",
            "can you ",
            "could you ",
            "do you ",
            "are you ",
            "is this ",
            "what is ",
            "what's ",
        )
        return lowered.startswith(question_starters)

    def _extract_name(self, message: str) -> str:
        """Extract a likely preferred name from common name-answer forms."""
        text = message.strip()
        patterns = [
            r"^(?:my name is|i am|i'm|call me|you can call me)\s+(.+)$",
            r"^(.+?)\s+(?:is fine|works|please)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip(" .,!?:;\"'")
        return text.strip(" .,!?:;\"'")

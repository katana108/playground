"""Build one runtime learner brief from the newer and older memory sources.

This service is the "single clipboard" for learner context. It merges:

- student_model.yaml (new learner notebook)
- memory.yaml (session summaries, psychological profile)
- profile.yaml (learner preferences only — no tutor character)
- tutor.yaml (per-user tutor name and persona; falls back to profile.character
  for legacy users who never created a tutor.yaml)

The result is intentionally compact enough to feed into routing and teaching
prompts without forcing each caller to know how four different stores work.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class LearnerBriefService:
    """Synthesize one learner brief for runtime use."""

    def __init__(self, data_service: Any, profile_service: Any = None):
        self.data_service = data_service
        self.profile_service = profile_service

    def build(self, user_id: str, student_model: Any = None) -> Dict[str, Any]:
        """Return a compact learner brief for one runtime turn."""
        student = student_model
        identity = getattr(student, "identity", {}) or {}
        goals = getattr(student, "goals_and_constraints", {}) or {}
        preferences = getattr(student, "stated_preferences_about_self", {}) or {}

        profile = self._load_profile(user_id)
        memory = self._load_memory(user_id)
        psychological = memory.get("psychological_profile", {}) if isinstance(memory, dict) else {}
        recent_sessions = list((memory.get("session_history", []) if isinstance(memory, dict) else []) or [])[-3:]
        weekly_summaries = list((memory.get("weekly_summaries", []) if isinstance(memory, dict) else []) or [])
        latest_weekly = weekly_summaries[-1] if weekly_summaries else {}

        learner_name = (
            identity.get("preferred_form_of_address")
            or identity.get("learner_name")
            or (profile.get("metadata", {}) or {}).get("learner_name")
            or ""
        )

        communication = dict((profile.get("communication", {}) or {}))
        interaction = dict((profile.get("interaction_preferences", {}) or {}))
        explanation_preferences = dict((profile.get("explanation_preferences", {}) or {}))
        character = dict((profile.get("character", {}) or {}))
        motivations = dict((profile.get("motivations", {}) or {}))

        # Tutor.yaml is the canonical source for tutor name + persona.
        # profile.character is the legacy fallback for users without tutor.yaml.
        tutor_config = self._load_tutor_config(user_id)
        tutor_name = str(tutor_config.get("name", "") or "").strip() or "Sofico"
        tutor_persona = str(tutor_config.get("persona", "") or "").strip() or None
        persona_description = tutor_persona or character.get("persona_description")

        brief = {
            "learner_name": learner_name,
            "identity": identity,
            "goals_and_constraints": goals,
            "stated_preferences_about_self": preferences,
            "study_goals": list(goals.get("study_goals", []) or []),
            "preferred_subjects": list(goals.get("preferred_subjects", []) or []),
            "learning_preferences": list(preferences.get("learning_preferences", []) or []),
            "direct_statements": list(preferences.get("direct_statements", []) or []),
            "inferred_profile": self._entry_summaries(getattr(student, "inferred_profile", []) or []),
            "progress_patterns": self._entry_summaries(getattr(student, "progress_patterns", []) or []),
            "relationship_memory": self._entry_summaries(getattr(student, "relationship_memory", []) or []),
            "psychological_profile": {
                "learning_style": str(psychological.get("learning_style", "") or ""),
                "strengths": list(psychological.get("strengths", []) or []),
                "growth_areas": list(psychological.get("growth_areas", []) or []),
                "resistance_patterns": list(psychological.get("resistance_patterns", []) or []),
                "best_strategies": list(psychological.get("best_strategies", []) or []),
            },
            "recent_sessions": self._recent_session_summaries(recent_sessions),
            "latest_weekly_summary": str(latest_weekly.get("report", "") or ""),
            "style": {
                "tutor_name": tutor_name,
                "archetype": str(character.get("archetype", "sophia") or "sophia"),
                "persona_description": persona_description,
                "motivation": str(motivations.get("primary", "curiosity") or "curiosity"),
                "communication": communication,
                "interaction_preferences": interaction,
                "explanation_preferences": explanation_preferences,
                "communication_style": {
                    "verbosity": communication.get("verbosity", "concise"),
                    "theatricality": communication.get("theatricality", "subtle"),
                    "humor_style": communication.get("humor_style", "light"),
                    "proactivity": interaction.get("proactivity", "medium"),
                    "customization_mode": interaction.get("customization_mode", "quick"),
                },
            },
        }

        brief["prompt_block"] = self.to_prompt_block(brief)
        return brief

    def to_prompt_block(self, brief: Optional[Dict[str, Any]]) -> str:
        """Format a learner brief into compact prompt text."""
        if not brief:
            return "No learner brief available yet."

        parts: List[str] = []
        learner_name = str(brief.get("learner_name", "") or "").strip()
        if learner_name:
            parts.append(f"- learner_name: {learner_name}")

        study_goals = list(brief.get("study_goals", []) or [])
        if study_goals:
            parts.append("- study_goals: " + "; ".join(study_goals[:4]))

        preferred_subjects = list(brief.get("preferred_subjects", []) or [])
        if preferred_subjects:
            parts.append("- preferred_subjects: " + "; ".join(preferred_subjects[:5]))

        learning_preferences = list(brief.get("learning_preferences", []) or [])
        if learning_preferences:
            parts.append("- learning_preferences: " + "; ".join(learning_preferences[:5]))

        inferred = list(brief.get("inferred_profile", []) or [])
        if inferred:
            parts.append("- inferred_profile: " + "; ".join(inferred[:5]))

        progress = list(brief.get("progress_patterns", []) or [])
        if progress:
            parts.append("- progress_patterns: " + "; ".join(progress[:5]))

        relationship = list(brief.get("relationship_memory", []) or [])
        if relationship:
            parts.append("- relationship_memory: " + "; ".join(relationship[:4]))

        psychological = dict(brief.get("psychological_profile", {}) or {})
        if psychological.get("learning_style"):
            parts.append(f"- learning_style: {psychological['learning_style']}")
        if psychological.get("strengths"):
            parts.append("- strengths: " + "; ".join((psychological.get("strengths") or [])[:4]))
        if psychological.get("growth_areas"):
            parts.append("- growth_areas: " + "; ".join((psychological.get("growth_areas") or [])[:4]))
        if psychological.get("resistance_patterns"):
            parts.append("- resistance_patterns: " + "; ".join((psychological.get("resistance_patterns") or [])[:3]))
        if psychological.get("best_strategies"):
            parts.append("- best_strategies: " + "; ".join((psychological.get("best_strategies") or [])[:3]))

        recent = list(brief.get("recent_sessions", []) or [])
        if recent:
            rendered = []
            for session in recent[:2]:
                summary = str(session.get("summary", "") or "").strip()
                if not summary:
                    continue
                topics = ", ".join(session.get("topics", []) or [])
                label = f"{session.get('date', '')} ({topics})".strip()
                rendered.append(f"{label}: {summary}" if label else summary)
            if rendered:
                parts.append("- recent_sessions: " + " | ".join(rendered))

        weekly = str(brief.get("latest_weekly_summary", "") or "").strip()
        if weekly:
            clipped = weekly[:350] + ("..." if len(weekly) > 350 else "")
            parts.append(f"- latest_weekly_summary: {clipped}")

        return "\n".join(parts) if parts else "No learner brief available yet."

    def _entry_summaries(self, entries: List[Any], limit: int = 6) -> List[str]:
        """Return active learner-memory summaries."""
        summaries: List[str] = []
        for entry in entries:
            status = getattr(entry, "status", "active")
            summary = str(getattr(entry, "summary", "") or "").strip()
            if status == "active" and summary:
                summaries.append(summary)
        return summaries[-limit:]

    def _recent_session_summaries(self, sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep only the parts of recent sessions that help runtime prompts."""
        compact: List[Dict[str, Any]] = []
        for session in sessions:
            compact.append(
                {
                    "date": str(session.get("date", "") or ""),
                    "topics": list(session.get("topics", []) or []),
                    "summary": str(session.get("summary", "") or ""),
                    "struggles": list(session.get("struggles", []) or []),
                    "strengths": list(session.get("strengths", []) or []),
                }
            )
        return compact

    def _load_profile(self, user_id: str) -> Dict[str, Any]:
        """Load legacy profile settings when available."""
        if self.profile_service:
            try:
                return self.profile_service.load_profile(user_id) or {}
            except Exception:
                return {}
        if self.data_service and hasattr(self.data_service, "load_profile"):
            try:
                return self.data_service.load_profile(user_id) or {}
            except Exception:
                return {}
        return {}

    def _load_tutor_config(self, user_id: str) -> Dict[str, Any]:
        """Load per-user tutor.yaml when available."""
        if self.data_service and hasattr(self.data_service, "load_tutor_config"):
            try:
                return dict(self.data_service.load_tutor_config(user_id) or {})
            except Exception:
                return {}
        return {}

    def _load_memory(self, user_id: str) -> Dict[str, Any]:
        """Load persisted memory summaries when available."""
        if self.data_service and hasattr(self.data_service, "load_memory"):
            try:
                return self.data_service.load_memory(user_id) or {}
            except Exception:
                return {}
        return {}

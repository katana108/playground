"""
Profile Service
Loads and interprets learner profiles for personalized interactions
"""

import os
import logging
import yaml
import copy
import re
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


VALID_ARCHETYPES = {"sophia", "sensei", "grandmother", "research-mentor"}
VALID_MOTIVATIONS = {"curiosity", "achievement", "play", "social"}
VALID_VERBOSITY = {"concise", "balanced", "chatty"}
VALID_THEATRICALITY = {"subtle", "expressive", "vivid"}
VALID_HUMOR = {"none", "light", "playful"}
VALID_PROACTIVITY = {"low", "medium", "high"}
VALID_EXPLANATION_STYLES = {"narrative", "logical-steps", "examples-first"}


class ProfileService:
    """
    Loads learner profiles and provides profile-aware response generation.

    Profiles contain:
    - Learning level and style
    - Motivations and drivers
    - Sensitivity to errors/failure
    - Feedback preferences
    - Metaphor preferences
    - Strengths and growth areas
    """

    def __init__(self, data_service=None):
        self.data_service = data_service
        self.profile_cache = {}  # Cache loaded profiles

    def load_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Load comprehensive learner profile.

        Returns profile dict with all settings, or defaults if not found.
        """
        # Check cache
        if user_id in self.profile_cache:
            return self.profile_cache[user_id]

        profile = self._get_default_profile()

        try:
            loaded = self.data_service.load_profile(user_id)
            if loaded:
                profile = self._deep_merge_dicts(profile, loaded)
                profile = self._sanitize_profile(profile, user_id)
                logger.info(f"Loaded profile for user {user_id}")
            else:
                logger.warning(f"No profile found for user {user_id}, using defaults")
        except Exception as e:
            logger.warning(f"Could not load profile for {user_id}: {e}")

        # Cache it
        self.profile_cache[user_id] = profile
        return profile

    def save_profile(self, user_id: str, profile: Dict[str, Any]):
        """Save a learner profile and invalidate the cache."""
        try:
            from services.local_file_service import LocalFileService
            if isinstance(self.data_service, LocalFileService):
                self.data_service.save_profile(user_id, profile)
                self.invalidate_cache(user_id)
                logger.info(f"Saved and cached profile for {user_id}")
        except Exception as e:
            logger.error(f"Could not save profile for {user_id}: {e}")
            raise

    def invalidate_cache(self, user_id: str):
        """Remove a user's profile from cache so the next load re-reads from disk."""
        if user_id in self.profile_cache:
            del self.profile_cache[user_id]

    def get_feedback_style(self, user_id: str) -> Dict[str, Any]:
        """Get feedback preferences for this learner"""
        profile = self.load_profile(user_id)

        return {
            "style": profile.get("feedback_preferences", {}).get("style", "analytical-encouraging"),
            "detail_level": profile.get("feedback_preferences", {}).get("detail_level", "medium"),
            "tone": profile.get("feedback_preferences", {}).get("tone", "formal-warm"),
            "directness": profile.get("feedback_preferences", {}).get("criticism_directness", "medium"),
            "praise_style": profile.get("feedback_preferences", {}).get("praise_style", "specific"),
            "use_emojis": profile.get("feedback_preferences", {}).get("use_emojis", False)
        }

    def get_sensitivity_level(self, user_id: str) -> Dict[str, str]:
        """Get sensitivity settings for this learner"""
        profile = self.load_profile(user_id)

        return {
            "error_sensitivity": profile.get("sensitivity", {}).get("error_sensitivity", "medium"),
            "failure_resilience": profile.get("sensitivity", {}).get("failure_resilience", "medium"),
            "frustration_threshold": profile.get("sensitivity", {}).get("frustration_threshold", "medium"),
            "imposter_syndrome": profile.get("sensitivity", {}).get("imposter_syndrome", "medium"),
            "perfectionism": profile.get("sensitivity", {}).get("perfectionism", "medium")
        }

    def get_metaphor_preferences(self, user_id: str) -> Dict[str, list]:
        """Get preferred and avoided metaphors"""
        profile = self.load_profile(user_id)
        comm = profile.get("communication", {})
        metaphors = comm.get("metaphor_preferences", {})

        return {
            "preferred": metaphors.get("preferred", ["natural-processes", "ancient-wisdom"]),
            "avoid": metaphors.get("avoid", [])
        }

    def get_communication_style(self, user_id: str) -> Dict[str, str]:
        """Get communication tuning preferences for this learner."""
        profile = self.load_profile(user_id)
        comm = profile.get("communication", {})
        interaction = profile.get("interaction_preferences", {})

        return {
            "verbosity": comm.get("verbosity", "concise"),
            "theatricality": comm.get("theatricality", "subtle"),
            "humor_style": comm.get("humor_style", "light"),
            "proactivity": interaction.get("proactivity", "medium"),
            "customization_mode": interaction.get("customization_mode", "quick"),
        }

    def get_learning_level(self, user_id: str, topic: Optional[str] = None) -> str:
        """
        Get learning level for user, optionally for specific topic.

        Returns: "beginner" | "intermediate" | "advanced"
        """
        profile = self.load_profile(user_id)
        level_config = profile.get("learning_level", {})

        # Check topic-specific override
        if topic:
            by_topic = level_config.get("by_topic", {})
            if topic in by_topic:
                return by_topic[topic]

        # Return general level
        return level_config.get("general", "intermediate")

    def build_personalized_system_prompt(
        self,
        user_id: str,
        context: str = "feedback",
        memory_context: str = "",
        preference_overrides: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build a personalized system prompt based on learner profile.

        Args:
            user_id: The learner
            context: "feedback" | "parsing" | "question" - what Sofi is doing

        Returns:
            Enhanced system prompt with learner-specific instructions
        """
        from config.personality import get_system_prompt, get_archetype_voice, get_archetype_feedback_style

        profile = self.load_profile(user_id)
        tutor_config = self._load_tutor_config(user_id)
        tutor_name = str(tutor_config.get("name", "") or "Sofico")
        persona_description = str(tutor_config.get("persona", "") or "").strip() or None

        # Fall back to legacy profile character block when no tutor.yaml exists
        character = profile.get("character", {})
        archetype = character.get("archetype", "sophia")
        if not persona_description:
            persona_description = character.get("persona_description") or None

        # Custom persona takes priority over preset archetype
        if persona_description:
            base_prompt = f"You are {tutor_name}, an educational tutor.\n\n{persona_description}"
            archetype_feedback = get_archetype_feedback_style(archetype)
        else:
            archetype_voice = get_archetype_voice(archetype)
            archetype_feedback = get_archetype_feedback_style(archetype)
            base_prompt = f"You are {tutor_name}, an educational tutor.\n\n{archetype_voice}"

        # Get profile-specific settings
        feedback = self.get_feedback_style(user_id)
        sensitivity = self.get_sensitivity_level(user_id)
        metaphors = self.get_metaphor_preferences(user_id)
        communication_style = self.get_communication_style(user_id)
        if preference_overrides:
            communication_style = {
                **communication_style,
                **preference_overrides.get("communication", {}),
                **preference_overrides.get("interaction_preferences", {}),
            }
        motivation = profile.get("motivations", {}).get("primary", "curiosity")

        verbosity_instructions = {
            "concise": "Keep replies compact by default — usually 2-4 sentences unless the learner asks for more depth.",
            "balanced": "Keep replies moderately detailed — enough to feel helpful without drifting into long monologues.",
            "chatty": "It is acceptable to be more expansive and conversational, but still stay coherent and useful.",
        }
        theatricality_instructions = {
            "subtle": "Keep the tone grounded and natural. Persona should color the voice lightly, not dominate it.",
            "expressive": "Let the persona show more clearly through word choice and rhythm, while staying readable and sincere.",
            "vivid": "Lean into a stylized persona voice more boldly, but stay clear, useful, and emotionally believable.",
        }
        humor_instructions = {
            "none": "Avoid jokes unless the learner explicitly invites them.",
            "light": "Use occasional light wit when it feels natural, but never let it crowd out clarity.",
            "playful": "A playful tone is welcome when appropriate, as long as the teaching stays sharp.",
        }
        proactivity_instructions = {
            "low": "Be restrained. Wait for explicit requests before suggesting new tasks or transitions.",
            "medium": "Offer collaborative suggestions when genuinely useful, but do not push or over-direct.",
            "high": "Be proactively helpful. Suggest next steps and useful structures more often, while still sounding collaborative.",
        }

        # Motivation-specific instructions
        motivation_instructions = {
            "curiosity": (
                "This learner is motivated by CURIOSITY — discovery is the reward.\n"
                "→ Highlight surprising patterns and unexpected connections.\n"
                "→ Use phrases like 'What's fascinating here is...' or 'Interestingly, this also appears in...'\n"
                "→ After a correct answer, offer a deeper 'did you know' angle when relevant."
            ),
            "achievement": (
                "This learner is motivated by ACHIEVEMENT — they want to see progress.\n"
                "→ Reference their improvement and milestones: 'You've mastered X, here's what's next.'\n"
                "→ Frame sessions as leveling up: 'This is the harder version of what you just got right.'\n"
                "→ Make progress visible and concrete."
            ),
            "play": (
                "This learner is motivated by PLAY — learning should feel fun and engaging.\n"
                "→ Keep the tone light and energetic.\n"
                "→ Use variety; avoid repetitive or dry phrasing.\n"
                "→ Make challenges feel like puzzles to solve, not tests to pass."
            ),
            "social": (
                "This learner is motivated by SOCIAL connection — they learn to help others.\n"
                "→ Frame knowledge as something to share: 'Imagine explaining this to a colleague...'\n"
                "→ Connect concepts to their impact on others or a larger purpose.\n"
                "→ Emphasize contribution: 'Understanding this makes you more useful to your team.'"
            ),
        }
        motivation_text = motivation_instructions.get(motivation, motivation_instructions["curiosity"])

        # Build personalization section
        personalization = f"""
## Learner Profile Adaptations

**Tutor: {tutor_name}{(' (custom persona)' if persona_description else ' — ' + archetype.upper())}**
- When correct: {archetype_feedback['on_correct']}
- When wrong: {archetype_feedback['on_wrong']}

**Primary Motivation: {motivation.upper()}**
{motivation_text}

**Feedback Style:** {feedback['style']}
- Tone: {feedback['tone']}
- Detail level: {feedback['detail_level']}
- Criticism directness: {feedback['directness']}
- Use emojis: {feedback['use_emojis']}

**Sensitivity:**
- Error sensitivity: {sensitivity['error_sensitivity']}
  {"→ This learner gets discouraged by mistakes. Be gentle and encouraging." if sensitivity['error_sensitivity'] == 'high' else ""}
  {"→ This learner views mistakes analytically. Give direct, honest feedback." if sensitivity['error_sensitivity'] == 'low' else ""}
- Imposter syndrome: {sensitivity['imposter_syndrome']}
  {"→ Provide reassurance about competence when appropriate." if sensitivity['imposter_syndrome'] == 'high' else ""}

**Communication Preferences:**
- Verbosity: {communication_style['verbosity']}
  {verbosity_instructions.get(communication_style['verbosity'], verbosity_instructions['concise'])}
- Theatricality: {communication_style['theatricality']}
  {theatricality_instructions.get(communication_style['theatricality'], theatricality_instructions['subtle'])}
- Humor style: {communication_style['humor_style']}
  {humor_instructions.get(communication_style['humor_style'], humor_instructions['light'])}
- Proactivity: {communication_style['proactivity']}
  {proactivity_instructions.get(communication_style['proactivity'], proactivity_instructions['medium'])}
- Preferred metaphors: {', '.join(metaphors['preferred'])}
  Use these types of metaphors when explaining concepts.
- Avoid metaphors: {', '.join(metaphors['avoid']) if metaphors['avoid'] else 'none'}
"""

        # Add context-specific guidance
        if context == "feedback":
            if sensitivity['error_sensitivity'] == 'low' and feedback['directness'] == 'high':
                personalization += """
**For this learner when giving feedback:**
- Be direct and precise — name what was wrong and why
- Skip excessive encouragement; this learner prefers honesty to comfort
- Correct clearly, in your archetype's voice"""
            elif sensitivity['error_sensitivity'] == 'high':
                personalization += """
**For this learner when giving feedback:**
- Be gentle and supportive
- Emphasize progress and effort
- Normalize mistakes as part of learning
- Celebrate small wins"""

        elif context == "chat":
            name = profile.get("metadata", {}).get("learner_name", "")
            if name:
                personalization += f"\n\nYou are talking with {name}. Use their name occasionally — not every message."
            personalization += """
**In conversation mode:**
- You do have access to recent chat history in this conversation and any saved learner profile or memory provided below.
- Never say you have no memory, that each conversation starts fresh, or that you cannot remember previous messages in this chat.
- If the learner asks what you remember, answer only from the context you actually have and be honest about limits without pretending total amnesia.
- You are curious about this person beyond their studies.
- Ask about their life, work, interests, and how they're doing.
- Everything you learn here helps you teach them better.
- If a learner profile already exists, do not restart onboarding or re-ask basic setup questions unless the learner clearly wants to update their preferences.
- Prioritize the learner's current request over gathering more background.
- Don't perform warmth — be genuinely interested."""

        if memory_context:
            personalization += f"\n\n{memory_context}"

        return base_prompt + "\n" + personalization

    def _load_tutor_config(self, user_id: str) -> Dict[str, Any]:
        if not self.data_service or not hasattr(self.data_service, "load_tutor_config"):
            return {}
        try:
            return dict(self.data_service.load_tutor_config(user_id) or {})
        except Exception:
            return {}

    def _deep_merge_dicts(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Merge nested profile data without dropping default branches."""
        merged = copy.deepcopy(base)
        for key, value in (updates or {}).items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge_dicts(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _sanitize_profile(self, profile: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Guard malformed profile fields so they do not poison runtime prompts."""
        profile = copy.deepcopy(profile)

        metadata = profile.setdefault("metadata", {})
        learner_name = metadata.get("learner_name")
        if learner_name and not self._is_valid_name(learner_name):
            logger.warning(f"Ignoring malformed learner_name for {user_id}: {learner_name!r}")
            metadata.pop("learner_name", None)

        character = profile.setdefault("character", {})
        archetype = character.get("archetype", "sophia")
        if archetype not in VALID_ARCHETYPES:
            logger.warning(f"Falling back from invalid archetype for {user_id}: {archetype!r}")
            character["archetype"] = "sophia"

        persona_description = character.get("persona_description")
        if persona_description and not self._is_sane_persona_description(persona_description):
            logger.warning(f"Ignoring suspicious persona_description for {user_id}")
            character["persona_description"] = None

        motivations = profile.setdefault("motivations", {})
        primary_motivation = motivations.get("primary")
        if primary_motivation not in VALID_MOTIVATIONS:
            if primary_motivation not in (None, ""):
                logger.warning(f"Falling back from invalid primary motivation for {user_id}: {primary_motivation!r}")
            motivations["primary"] = "curiosity"

        communication = profile.setdefault("communication", {})
        if communication.get("verbosity") not in VALID_VERBOSITY:
            communication["verbosity"] = "concise"
        if communication.get("theatricality") not in VALID_THEATRICALITY:
            communication["theatricality"] = "subtle"
        if communication.get("humor_style") not in VALID_HUMOR:
            communication["humor_style"] = "light"

        interaction = profile.setdefault("interaction_preferences", {})
        if interaction.get("proactivity") not in VALID_PROACTIVITY:
            interaction["proactivity"] = "medium"

        explanation = profile.setdefault("explanation_preferences", {})
        if explanation.get("style") not in VALID_EXPLANATION_STYLES:
            explanation["style"] = "narrative"

        return profile

    def _is_valid_name(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        name = value.strip()
        if len(name) < 2 or len(name) > 40:
            return False
        if any(char.isdigit() for char in name):
            return False
        lowered = name.lower()
        if lowered in {"friend", "learner", "user", "someone"}:
            return False
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z'\-\s]{1,39}", name))

    def _is_sane_persona_description(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        text = value.strip()
        if len(text) < 40 or len(text.split()) < 8 or len(text) > 600:
            return False
        if any(token in text for token in ["{", "}", "```"]):
            return False

        lowered = text.lower()
        noisy_fragments = [
            "start creating lessons",
            "quiz me",
            "explain it",
            "show progress",
            "save defaults",
            "looks good",
            "beginner yes",
            "course info",
        ]
        if any(fragment in lowered for fragment in noisy_fragments):
            return False
        if lowered.count("?") > 1:
            return False
        return True

    def _get_default_profile(self) -> Dict[str, Any]:
        """Default profile for learners without a profile.yaml"""
        return {
            "metadata": {},
            "character": {
                "archetype": "sophia",
                "persona_description": None,
            },
            "learning_level": {
                "general": "intermediate"
            },
            "feedback_preferences": {
                "style": "analytical-encouraging",
                "detail_level": "medium",
                "tone": "formal-warm",
                "use_emojis": False,
                "criticism_directness": "medium",
                "praise_style": "specific"
            },
            "sensitivity": {
                "error_sensitivity": "medium",
                "failure_resilience": "medium",
                "frustration_threshold": "medium",
                "imposter_syndrome": "medium",
                "perfectionism": "medium"
            },
            "communication": {
                "verbosity": "concise",
                "theatricality": "subtle",
                "humor_style": "light",
                "metaphor_preferences": {
                    "preferred": ["natural-processes", "ancient-wisdom"],
                    "avoid": []
                },
                "explanation_depth": "moderate"
            },
            "interaction_preferences": {
                "proactivity": "medium",
                "customization_mode": "quick",
                "preference_update_style": "confirm-before-saving"
            },
            "explanation_preferences": {
                "chunk_size": "medium",
                "style": "narrative",
            },
            "session_preferences": {
                "preferred_session_size": 15,
                "interleaving_enabled": True
            },
            "motivations": {
                "primary": "curiosity"
            }
        }

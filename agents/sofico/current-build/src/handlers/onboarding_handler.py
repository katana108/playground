"""
Onboarding Handler
LLM-driven conversational profile setup. No state machine — Claude conducts
a natural conversation and extracts profile data when it has everything it needs.

Triggered by: "customize", "my preferences", "set up profile"
Also auto-triggered for new users with no profile on first greeting.
"""

import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Dict, Any

import anthropic

from llm_utils import MODEL_DEFAULT, llm_text

logger = logging.getLogger(__name__)

ONBOARDING_STATE_MAX_AGE_HOURS = 2

ONBOARDING_SYSTEM_PROMPT = """You are Sofi, a warm and curious learning companion. You are meeting a learner and want to understand how to teach them best.

Your goal is to naturally discover these things through friendly conversation:
1. Their **name**
2. Their preferred **teaching persona** — how they like to be taught. Ask them to describe their ideal teacher in their own words. You may offer examples as inspiration, but don't force them into categories:
   - A wise, philosophical mentor who asks questions and lets you discover answers (Socratic)
   - A direct, disciplined sensei who demands precision and doesn't soften corrections
   - A warm, patient grandmother who celebrates every small win and never rushes
   - A rigorous research mentor who treats you as a peer and pushes for evidence
   - Or something entirely different — let them describe it freely
   Once you understand what they want, translate it into a short teaching voice description (2-4 sentences) that captures their ideal guide's tone, style, and personality. This will be used to shape how Sofi teaches them.
3. What **motivates** them to learn:
   - *curiosity*: loves figuring things out, discovery is the reward
   - *achievement*: loves seeing progress and leveling up
   - *play*: wants it to be fun and engaging, like a game
   - *social*: learns to help others or be part of something bigger
4. How they handle **mistakes** (error_sensitivity):
   - *low*: wants direct feedback, no softening needed
   - *medium*: analytical and conversational about errors
   - *high*: gets discouraged by mistakes, needs gentle encouragement
5. Their **background** — what they already know well and what they're curious about
6. Their preferred **explanation style**:
   - *narrative*: flowing story-like explanation, connected naturally
   - *logical-steps*: step by step, each building on the last
   - *examples-first*: concrete example first, then the principle
7. **Metaphor preferences** — what kinds of metaphors resonate:
   - *natural-processes*: nature, seasons, ecosystems, rivers
   - *ancient-wisdom*: philosophy, historical figures, mythology
   - *technology*: systems, code, machines, networks
   - *human-experience*: everyday life, relationships, work
   - *scientific*: physics, biology, chemistry analogies
8. Optional **advanced tuning** — only ask if they want finer control, or if they mention these preferences on their own:
   - *verbosity*: concise, balanced, chatty
   - *proactivity*: low, medium, high
   - *theatricality*: subtle, expressive, vivid
   - *humor_style*: none, light, playful

Guidelines:
- Be genuinely warm and curious, not clinical or formal
- Ask 1-2 things at a time — don't bombard them with questions
- If they give a vague or unexpected answer, explore it with a follow-up question
- Keep your responses short: 2-4 sentences
- It's fine if the conversation takes several turns — that's natural
- Default to a **quick setup** first. Once you understand the core teaching preferences, you may ask if they want to fine-tune anything further. If they do not care, use sensible defaults for advanced tuning.
- **Name is optional**: if the learner declines to share their name, prefers to stay anonymous, or clearly doesn't want to give it, accept that warmly and use "friend" as the name. Never push for a name more than once.
- **After 10 exchanges**: if you still don't have all fields, make reasonable inferences from what you do know and complete the profile. Don't leave the learner stuck forever.

When you are confident you have clear answers for all fields (or have made reasonable inferences), end your message with this exact line (on its own line at the very end, no extra text after it):
PROFILE_COMPLETE:{"name":"...","persona_description":"...","archetype":"...","motivation":"...","error_sensitivity":"...","background":"...","explanation_style":"...","metaphors":["..."],"verbosity":"...","proactivity":"...","theatricality":"...","humor_style":"...","customization_mode":"..."}

- "persona_description": 2-4 sentences describing the ideal teaching voice you crafted with the learner
- "archetype": closest preset match — sophia, sensei, grandmother, or research-mentor (used as fallback)
- Valid motivation values: curiosity, achievement, play, social
- Valid error_sensitivity values: low, medium, high
- Valid explanation_style values: narrative, logical-steps, examples-first
- Valid metaphors values (list, pick 1-2): natural-processes, ancient-wisdom, technology, human-experience, scientific
- Valid verbosity values: concise, balanced, chatty
- Valid proactivity values: low, medium, high
- Valid theatricality values: subtle, expressive, vivid
- Valid humor_style values: none, light, playful
- Valid customization_mode values: quick, advanced

If advanced tuning was not discussed, use defaults:
- verbosity: concise
- proactivity: medium
- theatricality: subtle
- humor_style: light
- customization_mode: quick"""

ERROR_STYLE_MAP = {
    "low": {
        "error_sensitivity": "low",
        "criticism_directness": "high",
        "feedback_style": "direct",
    },
    "medium": {
        "error_sensitivity": "medium",
        "criticism_directness": "medium",
        "feedback_style": "analytical-encouraging",
    },
    "high": {
        "error_sensitivity": "high",
        "criticism_directness": "low",
        "feedback_style": "encouraging",
    },
}


class OnboardingHandler:
    """
    Manages conversational profile setup using Claude.
    No state machine — the LLM conducts the conversation and signals
    completion by outputting PROFILE_COMPLETE: followed by JSON.

    active_onboardings: user_id → { history: [...], is_update: bool }
    """

    def __init__(self, data_service, profile_service, session_response_service=None):
        self.data_service = data_service
        self.profile_service = profile_service
        self.response_service = session_response_service
        self.active_onboardings: Dict[str, Dict[str, Any]] = {}
        self._state_notices: Dict[str, str] = {}
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = MODEL_DEFAULT

    def is_active(self, user_id: str) -> bool:
        if user_id in self.active_onboardings:
            if self._is_state_stale(user_id, self.active_onboardings[user_id]):
                self._state_notices[user_id] = (
                    "That earlier setup flow expired, so I cleared it. We can continue with what you want now."
                )
                self.clear(user_id)
                return False
            return True
        # Recover state after bot restart
        state = self.data_service.load_onboarding_state(user_id)
        if state and state.get("history"):
            if self._is_state_stale(user_id, state):
                self._state_notices[user_id] = (
                    "That earlier setup flow expired, so I cleared it. We can continue with what you want now."
                )
                self.clear(user_id)
                return False
            self.active_onboardings[user_id] = state
            return True
        return False

    def start(self, user_id: str, say, is_update: bool = False, opening: str = None):
        """Begin the onboarding conversation.

        If opening is provided (e.g. Sofi's acknowledgment from get_sofi_response),
        use it directly instead of generating a new one — avoids sending two messages.
        """
        if not opening:
            learner_name = ""
            if is_update:
                existing_profile = self.profile_service.load_profile(user_id)
                learner_name = existing_profile.get("metadata", {}).get("learner_name", "")

            if self.response_service:
                opening = self.response_service.generate_onboarding_opening(learner_name, is_update)
            elif is_update:
                opening = f"Let's update your preferences{', ' + learner_name if learner_name else ''}. What would you like to change?"
            else:
                opening = "Welcome! I'm Sofi, your learning companion. What's your name?"

        session = {
            "history": [{"role": "assistant", "content": opening}],
            "is_update": is_update,
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.active_onboardings[user_id] = session
        self._save_state(user_id)
        say(opening)

    def handle(self, event, say):
        """Process a user message during onboarding."""
        user_id = event.get("user")
        text = event.get("text", "").strip()

        if user_id not in self.active_onboardings:
            return

        session = self.active_onboardings[user_id]
        history = session["history"]
        text_lower = text.lower()

        if any(phrase in text_lower for phrase in {"cancel setup", "cancel onboarding", "stop setup", "stop onboarding"}):
            self._cancel_onboarding(user_id, say)
            return

        if self._is_stuck(session) and any(phrase in text_lower for phrase in {"save defaults", "save profile"}):
            fallback_profile = self._build_fallback_profile_data(session)
            self._save_and_confirm(user_id, fallback_profile, say)
            return

        if self._is_stuck(session) and any(phrase in text_lower for phrase in {"continue", "keep going"}):
            say("All right. We'll keep refining it together.")
            return

        history.append({"role": "user", "content": text})

        # Force-complete after 10 user turns — the LLM won't reliably self-terminate
        user_turns = sum(1 for m in history if m.get("role") == "user")
        if user_turns >= 10:
            logger.info(f"Force-completing onboarding for {user_id} after {user_turns} turns")
            profile_data = self._extract_profile_from_history(history)
            say("Got it — I have enough to work with. Let me save your profile now.")
            self._save_and_confirm(user_id, profile_data, say)
            return

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=400,
                system=self._build_system_prompt(
                    history,
                    user_id=user_id,
                    is_update=session.get("is_update", False),
                ),
                messages=history,
            )
            reply = llm_text(response)
        except Exception as e:
            logger.error(f"Error in onboarding LLM call for {user_id}: {e}")
            say("I'm having a little trouble right now — please try again in a moment.")
            return

        parsed = self._extract_marker_json(reply, "PROFILE_COMPLETE")
        if parsed:
            conversational_part, profile_data = parsed
            if conversational_part:
                say(conversational_part)

            try:
                self._save_and_confirm(user_id, profile_data, say)
            except KeyError as e:
                logger.error(f"Failed to save parsed profile for {user_id}: {e} | raw: {reply}")
                # Keep conversation going rather than crashing
                history.append({"role": "assistant", "content": conversational_part or reply})
                self._save_state(user_id)
        else:
            history.append({"role": "assistant", "content": reply})
            # Keep last 40 messages — enough to preserve early context (e.g. topic lists)
            if len(history) > 40:
                session["history"] = history[-40:]
            self._save_state(user_id)
            if self._is_stuck(session):
                say(
                    f"{reply}\n\n"
                    f"_If this setup feels stuck, you can say `save defaults` to finish with sensible defaults, "
                    f"`continue` to keep refining, or `cancel setup` to leave for now._"
                )
            else:
                say(reply)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_system_prompt(self, history: list, user_id: str = "", is_update: bool = False) -> str:
        """Build system prompt, marking already-known goals as complete inside the goals list."""
        prompt = ONBOARDING_SYSTEM_PROMPT
        existing_name = ""
        if is_update and user_id:
            profile = self.profile_service.load_profile(user_id)
            existing_name = profile.get("metadata", {}).get("learner_name", "")
            if existing_name:
                prompt += (
                    f"\n\nThis is an UPDATE to an existing learner profile, not a first meeting. "
                    f"The learner is already known as {existing_name}. Do not ask for their name again unless "
                    f"they explicitly say they want to change it. Focus on what they want to adjust."
                )

        name = self._extract_name_from_history(history) or existing_name
        if not name:
            return prompt

        # Replace the name goal line with a completed marker so the LLM sees it as done
        # and skips asking for it. Modifying inside the goals list is more reliable than
        # a prefix rule, because the LLM follows the numbered list closely.
        return prompt.replace(
            "1. Their **name**",
            f"1. Their **name** — ✓ COMPLETE: the learner's name is {name}. Do NOT ask for it again.",
            1
        )

    def _extract_name_from_history(self, history: list) -> str:
        """Return the learner's name if it has been established in the conversation.

        Only uses user messages (reliable) — not assistant messages, which are noisy
        and cause false positives when regex with IGNORECASE matches common words.
        """
        NOT_NAMES = {
            "a", "an", "the", "not", "it", "i", "ok", "okay", "yes", "no",
            "hi", "hey", "hello", "just", "but", "and", "or", "so", "then",
        }

        for msg in history:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            stripped = content.strip()

            # "my name is X" / "call me X" / "i'm X" / "i am X"
            m = re.search(
                r"\b(?:my name is|call me|i(?:'m| am))\s+([A-Z][a-zA-Z'\-]{1,20})",
                content
            )
            if m:
                candidate = m.group(1).strip()
                if candidate.lower() not in NOT_NAMES:
                    return candidate

            # A bare name on its own line, optionally followed by another answer below it.
            first_line = stripped.splitlines()[0].strip() if stripped else ""
            if re.fullmatch(r"[A-Z][a-zA-Z'\-]{1,20}", first_line):
                if first_line.lower() not in NOT_NAMES:
                    return first_line

            # "Name but ..." or "Name, ..." — a capitalised word at the start
            # followed by "but", "but before", punctuation, or "and"
            m = re.match(
                r"^([A-Z][a-z]{1,20})\s*(?:but\b|,\b|and\b)",
                content.strip()
            )
            if m:
                candidate = m.group(1).strip()
                if candidate.lower() not in NOT_NAMES:
                    return candidate

        return ""

    def _save_state(self, user_id: str):
        try:
            if user_id in self.active_onboardings:
                self.active_onboardings[user_id]["updated_at"] = datetime.now().isoformat()
            self.data_service.save_onboarding_state(user_id, self.active_onboardings[user_id])
        except Exception as e:
            logger.warning(f"Could not persist onboarding state for {user_id}: {e}")

    def _cancel_onboarding(self, user_id: str, say):
        """Exit onboarding cleanly if the learner wants out."""
        self.clear(user_id)
        say("Okay. I’ll leave setup here. We can come back to it whenever you want.")

    def clear(self, user_id: str):
        """Drop onboarding state from memory and persistence."""
        self.active_onboardings.pop(user_id, None)
        self.data_service.clear_onboarding_state(user_id)

    def take_state_notice(self, user_id: str) -> str:
        """Return and clear any stale-state notice for the router."""
        return self._state_notices.pop(user_id, "")

    def _is_state_stale(self, user_id: str, session: Dict[str, Any]) -> bool:
        """Avoid resurrecting old onboarding/update sessions forever."""
        updated_at = session.get("updated_at") or session.get("started_at")
        if updated_at:
            try:
                ts = datetime.fromisoformat(updated_at)
                if datetime.now() - ts > timedelta(hours=ONBOARDING_STATE_MAX_AGE_HOURS):
                    logger.info(f"Onboarding state for {user_id} expired due to age")
                    return True
            except ValueError:
                logger.warning(f"Invalid onboarding timestamp for {user_id}: {updated_at}")

        # Backward-compatible cleanup for old saved update sessions with no timestamp.
        if session.get("is_update"):
            profile = self.profile_service.load_profile(user_id)
            if profile.get("metadata", {}).get("learner_name") and not updated_at:
                logger.info(f"Clearing legacy update-onboarding state for {user_id}")
                return True
        return False

    def _is_stuck(self, session: Dict[str, Any]) -> bool:
        """Return True when onboarding has gone on long enough to warrant an escape hatch."""
        user_turns = sum(1 for item in session.get("history", []) if item.get("role") == "user")
        return user_turns >= 6

    def _extract_profile_from_history(self, history: list) -> dict:
        """Use a dedicated LLM call to extract the full profile from the conversation.

        Separates extraction from conversation so the LLM can read everything said
        and produce accurate values rather than relying on the fallback defaults.
        Falls back to _build_fallback_profile_data if the LLM call fails.
        """
        extraction_prompt = (
            "You are a profile extractor. Read the onboarding conversation below and "
            "return a single JSON object with EXACTLY these keys (use defaults if unclear):\n"
            '{"name":"...","persona_description":"2-4 sentences describing ideal teaching voice",'
            '"archetype":"sophia|sensei|grandmother|research-mentor",'
            '"motivation":"curiosity|achievement|play|social",'
            '"error_sensitivity":"low|medium|high",'
            '"background":"what the learner already knows",'
            '"explanation_style":"narrative|logical-steps|examples-first",'
            '"metaphors":["natural-processes|ancient-wisdom|technology|human-experience|scientific"],'
            '"verbosity":"concise|balanced|chatty",'
            '"proactivity":"low|medium|high",'
            '"theatricality":"subtle|expressive|vivid",'
            '"humor_style":"none|light|playful",'
            '"customization_mode":"quick|advanced"}\n\n'
            "Defaults if not mentioned: archetype=sophia, motivation=curiosity, "
            "error_sensitivity=medium, explanation_style=narrative, metaphors=[human-experience], "
            "verbosity=concise, proactivity=medium, theatricality=subtle, humor_style=light, "
            "customization_mode=quick.\n\n"
            "Return ONLY the JSON object, nothing else."
        )
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=600,
                system=extraction_prompt,
                messages=history,
            )
            raw = llm_text(response)
            profile_data = self._extract_json_value(raw)
            if profile_data and isinstance(profile_data, dict) and "name" in profile_data:
                logger.info(f"Extracted profile via LLM for force-complete: {list(profile_data.keys())}")
                return profile_data
        except Exception as e:
            logger.warning(f"Profile extraction LLM call failed: {e}")

        return self._build_fallback_profile_data({"history": history})

    def _build_fallback_profile_data(self, session: Dict[str, Any]) -> dict:
        """Infer a minimal profile from the conversation so the learner can escape a loop."""
        history = session.get("history", [])
        user_messages = [
            item.get("content", "").strip()
            for item in history
            if item.get("role") == "user" and item.get("content")
        ]
        combined = " ".join(user_messages)
        recent_text = " ".join(user_messages[-3:]) if user_messages else ""

        name = "friend"
        name_match = re.search(r"\b(?:i(?:'m| am)|my name is|call me)\s+([A-Za-z][A-Za-z'\-]{1,30})", combined, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip().title()

        customization_mode = "advanced" if any(
            word in combined.lower() for word in ("verbosity", "proactive", "theatrical", "humor", "chatty", "concise")
        ) else "quick"

        return {
            "name": name,
            "persona_description": recent_text or "A calm, intelligent, concise tutor who adapts to the learner.",
            "archetype": "sophia",
            "motivation": "curiosity",
            "error_sensitivity": "medium",
            "background": recent_text or "Background not fully specified yet.",
            "explanation_style": "narrative",
            "metaphors": ["human-experience"],
            "verbosity": "concise",
            "proactivity": "medium",
            "theatricality": "subtle",
            "humor_style": "light",
            "customization_mode": customization_mode,
        }

    def _extract_marker_json(self, text: str, marker: str):
        """Find marker anywhere in the response and decode the JSON payload after it."""
        match = re.search(rf"{re.escape(marker)}\s*:\s*", text)
        if not match:
            return None

        conversational_part = text[:match.start()].strip()
        payload = text[match.end():].strip()
        parsed = self._extract_json_value(payload)
        if parsed is None:
            logger.warning(f"Could not parse {marker} payload. Raw: {payload[:200]}")
            return None
        return conversational_part, parsed

    def _extract_json_value(self, text: str):
        """Decode the first JSON object or array found in arbitrary text."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        decoder = json.JSONDecoder()
        for idx, char in enumerate(cleaned):
            if char not in "{[":
                continue
            try:
                value, _ = decoder.raw_decode(cleaned[idx:])
                return value
            except json.JSONDecodeError:
                continue
        return None

    def _save_and_confirm(self, user_id: str, profile_data: dict, say):
        """Build and save the profile, then send confirmation in archetype voice."""
        session = self.active_onboardings.get(user_id, {})
        is_update = session.get("is_update", False)
        existing_profile = self.profile_service.load_profile(user_id) if is_update else {}
        existing_name = existing_profile.get("metadata", {}).get("learner_name", "")

        name = existing_name or profile_data.get("name", "Learner")
        archetype = profile_data.get("archetype", "sophia")
        persona_description = profile_data.get("persona_description") or None
        motivation = profile_data.get("motivation", "curiosity")
        error_sensitivity = profile_data.get("error_sensitivity", "medium")
        background = profile_data.get("background", "")
        verbosity = profile_data.get("verbosity", "concise")
        proactivity = profile_data.get("proactivity", "medium")
        theatricality = profile_data.get("theatricality", "subtle")
        humor_style = profile_data.get("humor_style", "light")
        customization_mode = profile_data.get("customization_mode", "quick")

        # Normalise archetype in case LLM output slightly off
        valid_archetypes = {"sophia", "sensei", "grandmother", "research-mentor"}
        if archetype not in valid_archetypes:
            archetype = "sophia"

        if verbosity not in {"concise", "balanced", "chatty"}:
            verbosity = "concise"
        if proactivity not in {"low", "medium", "high"}:
            proactivity = "medium"
        if theatricality not in {"subtle", "expressive", "vivid"}:
            theatricality = "subtle"
        if humor_style not in {"none", "light", "playful"}:
            humor_style = "light"
        if customization_mode not in {"quick", "advanced"}:
            customization_mode = "quick"

        error_prefs = ERROR_STYLE_MAP.get(error_sensitivity, ERROR_STYLE_MAP["medium"])

        created_date = existing_profile.get("metadata", {}).get("created", date.today().isoformat())
        learning_level = existing_profile.get("learning_level", {}).get("general", "intermediate")
        session_preferences = existing_profile.get("session_preferences", {
            "preferred_session_size": 15,
            "interleaving_enabled": True,
        })

        profile = {
            "metadata": {
                "learner_name": name,
                "created": created_date,
                "last_updated": date.today().isoformat(),
            },
            "character": {
                "archetype": archetype,
                "persona_description": persona_description,
            },
            "learning_level": {
                "general": learning_level,
            },
            "motivations": {
                "primary": motivation,
            },
            "sensitivity": {
                "error_sensitivity": error_prefs["error_sensitivity"],
            },
            "feedback_preferences": {
                "style": error_prefs["feedback_style"],
                "criticism_directness": error_prefs["criticism_directness"],
                "tone": "formal-warm",
                "detail_level": "medium",
                "use_emojis": False,
            },
            "interests": {
                "background_knowledge": [background],
            },
            "explanation_preferences": {
                "chunk_size": "medium",
                "style": profile_data.get("explanation_style", "narrative"),
            },
            "communication": {
                "verbosity": verbosity,
                "theatricality": theatricality,
                "humor_style": humor_style,
                "metaphor_preferences": {
                    "preferred": profile_data.get("metaphors", ["natural-processes"]),
                    "avoid": []
                },
                "explanation_depth": "moderate"
            },
            "interaction_preferences": {
                "proactivity": proactivity,
                "customization_mode": customization_mode,
                "preference_update_style": "confirm-before-saving",
            },
            "session_preferences": {
                "preferred_session_size": session_preferences.get("preferred_session_size", 15),
                "interleaving_enabled": session_preferences.get("interleaving_enabled", True),
            },
        }

        try:
            self.data_service.save_profile(user_id, profile)
            self.profile_service.invalidate_cache(user_id)
            logger.info(f"Saved onboarding profile for {user_id}")
        except Exception as e:
            logger.error(f"Failed to save profile for {user_id}: {e}")
            say("I had trouble saving your profile. Please try again later.")
            del self.active_onboardings[user_id]
            return

        if self.response_service:
            confirmation = self.response_service.generate_onboarding_confirmation(
                name,
                persona_description=persona_description or "",
                archetype=archetype,
            )
        else:
            confirmation = f"Profile saved, {name}. Say *quiz me* whenever you're ready."
        say(confirmation)

        del self.active_onboardings[user_id]
        self.data_service.clear_onboarding_state(user_id)

    def persist_partial_profile(self, user_id: str):
        """Save a best-effort profile silently before leaving onboarding."""
        session = self.active_onboardings.get(user_id)
        if not session:
            return
        if not any(item.get("role") == "user" for item in session.get("history", [])):
            return
        fallback_profile = self._build_fallback_profile_data(session)
        self._save_and_confirm(user_id, fallback_profile, lambda *_args, **_kwargs: None)

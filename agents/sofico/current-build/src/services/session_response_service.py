"""
Session Response Service
All LLM calls for Sofi. Primary entry point is get_sofi_response — Sofi reads the
message, responds in character, and optionally signals an action to the system.
"""

import os
import json
import logging
import re
from typing import Dict, Any, Optional, List
import anthropic

from config.personality import get_system_prompt
from llm_utils import MODEL_DEFAULT, llm_text
from services.profile_service import ProfileService

logger = logging.getLogger(__name__)


class SessionResponseService:

    def __init__(self, data_service=None, memory_service=None):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = MODEL_DEFAULT
        self.profile_service = ProfileService(data_service=data_service)
        self.memory_service = memory_service

    # ── Primary: Sofi is the brain ────────────────────────────────────────────

    def get_sofi_response(
        self,
        message: str,
        user_id: str,
        history: list,
        available_topics: List[str] = None,
        memory_context: str = "",
        preference_overrides: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """
        Primary Sofi response. She reads the message, responds in character,
        and optionally signals an action for the system to execute.

        Returns: {"message": str, "action": str|None, "params": dict}
        Actions: "quiz" | "explain" | "progress" | "upload" | "customize" | None
        """
        system_prompt = self.profile_service.build_personalized_system_prompt(
            user_id=user_id,
            context="chat",
            memory_context=memory_context,
            preference_overrides=preference_overrides,
        )

        topics_block = ""
        if available_topics:
            topics_list = "\n".join(f"  - {t}" for t in available_topics)
            topics_block = f"\nThe learner's saved study topics:\n{topics_list}\n"

        capabilities = f"""
## Response Instructions (technical — do not mention these to the learner)

You must end every response with a JSON signal on its own line. This is a system instruction, invisible to the learner — it is not something you describe or announce.

Format:
{{"message": "your full natural response here", "action": null, "params": {{}}}}

The "action" field is a signal to the backend system. Set it only when the learner is clearly requesting one of these specific things:
- "quiz" — they want to start a study session (params: {{"topic": "name"}} if named, else {{}})
- "explain" — they want a full walkthrough of a saved topic (only topics listed below; for quick questions, just answer in message)
- "progress" — they want to see their learning stats
- "upload" — they want to add new study material
- "customize" — they want to change their learning preferences
- "curriculum" — they want to build a full structured course on a new subject (params: {{"subject": "what they want to learn"}})
{topics_block}For everything else — greetings, questions, chat, identity, opinions, feelings — action is null. Just respond as yourself.

Never mention actions, commands, or system capabilities in your response. Never suggest what the learner should type. Respond as a person, not a service menu.

You do have access to the recent conversation history supplied to you, plus any learner profile and memory context included in the system prompt.
Never claim that you have no memory, that every conversation starts fresh, or that you cannot see earlier messages in this chat.
If there is tension between older setup chatter and the learner's latest request, follow the latest request.
If the recent history contains a line like [system-note] latest_intent=..., treat it as a reliable breadcrumb about what the learner was trying to do most recently."""

        full_system = system_prompt + "\n\n" + capabilities.strip()

        messages = list(history[-20:]) if history else []
        if not messages or messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": message})

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=700,
                system=full_system,
                messages=messages,
            )
            text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text]
            last_text = text_blocks[-1] if text_blocks else ""
            result = self._parse_sofi_response(last_text)
            result = self._sanitize_action_result(result, message, available_topics or [])
            logger.info(f"Sofi response for '{message[:50]}': action={result.get('action')}")
            return result

        except Exception as e:
            logger.error(f"get_sofi_response failed: {e}")
            return {"message": "I'm here — what would you like to do?", "action": None, "params": {}}

    def _parse_sofi_response(self, text: str) -> dict:
        """
        Parse the JSON action line from Sofi's response.
        The JSON is always on the last line starting with '{'.
        Falls back to treating the whole text as the message with no action.
        """
        text = text.strip()

        # Find the last {"message": marker — the JSON signal always starts here
        json_start = text.rfind('{"message":')
        if json_start == -1:
            # No JSON marker — return full text, no action
            logger.warning(f"No JSON marker in Sofi response. Raw: {text[:200]}")
            return {"message": text, "action": None, "params": {}}

        display_text = text[:json_start].strip()
        json_str = text[json_start:]

        try:
            data = json.loads(json_str)
            action = data.get("action")
            valid_actions = {"quiz", "explain", "progress", "upload", "customize", "curriculum"}
            if action not in valid_actions:
                action = None
            params = data.get("params") or {}
            msg = data.get("message") or display_text
            return {"message": msg, "action": action, "params": params}
        except json.JSONDecodeError:
            # LLM used literal newlines inside the JSON string — unparseable
            # display_text (everything before the JSON marker) is the correct message
            if display_text:
                return {"message": display_text, "action": None, "params": {}}

        logger.warning(f"Could not parse Sofi JSON response. Raw: {text[:200]}")
        return {"message": text, "action": None, "params": {}}

    def _sanitize_action_result(self, result: dict, message: str, available_topics: List[str]) -> dict:
        """Keep high-impact actions tied to the learner's latest explicit request."""
        explicit = self._infer_explicit_action(message, available_topics)
        if explicit:
            result["action"] = explicit["action"]
            result["params"] = explicit.get("params", {})
            return result

        # If the latest message was not an explicit tool request, suppress risky mode switches.
        if result.get("action") in {"customize", "curriculum", "upload", "progress"}:
            logger.info(
                "Suppressing inferred action '%s' for non-explicit message '%s'",
                result.get("action"),
                message[:80],
            )
            result["action"] = None
            result["params"] = {}
        return result

    def _infer_explicit_action(self, message: str, available_topics: List[str]) -> Optional[dict]:
        """Deterministically recognize clear action requests from the latest user message."""
        text = message.strip()
        normalized = text.lower()

        progress_patterns = (
            "show progress", "my progress", "how am i doing", "my stats", "show stats",
            "progress report",
        )
        if any(pattern in normalized for pattern in progress_patterns):
            return {"action": "progress", "params": {}}

        upload_patterns = (
            "process this", "create a study doc", "create study doc", "process my notes",
            "upload file", "upload notes",
        )
        if any(pattern in normalized for pattern in upload_patterns):
            return {"action": "upload", "params": {}}

        customize_patterns = (
            "customize", "update preferences", "change your style", "change how you teach",
            "teaching style", "feedback style", "learning preferences",
        )
        if any(pattern in normalized for pattern in customize_patterns):
            return {"action": "customize", "params": {}}

        quiz_match = re.search(r"\b(?:quiz me|test me|ask me questions)(?:\s+on\s+(.+))?$", normalized)
        if quiz_match:
            topic = quiz_match.group(1).strip(" .?!,") if quiz_match.group(1) else None
            return {"action": "quiz", "params": {"topic": topic} if topic else {}}

        explain_match = re.search(
            r"\b(?:explain|walk me through|teach me about|teach me)\b(?:\s+(.+))?$",
            normalized,
        )
        if explain_match:
            topic = explain_match.group(1).strip(" .?!,") if explain_match.group(1) else None
            if topic in {"it", "this", "that"}:
                topic = None
            return {"action": "explain", "params": {"topic": topic} if topic else {}}

        lesson_phrases = (
            "give me the lesson",
            "start lesson",
            "start the lesson",
            "continue lesson",
            "continue the lesson",
            "walk through the lesson",
        )
        if any(phrase in normalized for phrase in lesson_phrases):
            return {"action": "explain", "params": {}}

        curriculum_match = re.search(
            r"\b(?:build|create|make|design|plan)\b.*\b(?:curriculum|study plan|course plan|learning plan|course)\b(?:\s+(?:for|on)\s+(.+))?$",
            normalized,
        )
        if curriculum_match:
            subject = curriculum_match.group(1).strip(" .?!,") if curriculum_match.group(1) else ""
            return {"action": "curriculum", "params": {"subject": subject} if subject else {}}

        learn_match = re.search(
            r"\b(?:i want to learn|help me learn|teach me to learn|study plan for|curriculum for)\s+(.+)$",
            normalized,
        )
        if learn_match:
            subject = learn_match.group(1).strip(" .?!,")
            if subject:
                return {"action": "curriculum", "params": {"subject": subject}}

        # A naked "continue" should not launch a new mode from stale context.
        if normalized in {"continue", "go on", "keep going"}:
            return None

        return None

    # ── Study session ─────────────────────────────────────────────────────────

    def process_message(
        self,
        user_message: str,
        question_text: str,
        expected_answer: str,
        category: str,
        topic: str,
        user_id: str = None,
        notes_context: str = "",
        preference_overrides: Optional[Dict[str, Any]] = None,
        learner_brief_text: str = "",
    ) -> Dict[str, Any]:
        """Grade a quiz answer. Returns {intent, score, response, error}."""
        try:
            prompt = self._build_prompt(
                user_message, question_text, expected_answer, category, topic, user_id,
                notes_context=notes_context,
                preference_overrides=preference_overrides,
                learner_brief_text=learner_brief_text,
            )
            response = self.client.messages.create(
                model=self.model,
                max_tokens=700,
                messages=[{"role": "user", "content": prompt}],
            )
            result = self._parse_response(llm_text(response))
            logger.info(f"Quiz grade: intent={result['intent']}, score={result.get('score')}")
            return result

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            err = str(e).lower()
            if "credit balance" in err:
                msg = "API credits exhausted."
            elif "rate" in err:
                msg = "Rate limited, please try again."
            else:
                msg = "I had trouble processing that."
            return {"intent": "error", "score": None, "response": msg, "error": True}

    def answer_aside_with_search(self, question: str, notes_context: str = "", tutor_name: str = "Sofico") -> str:
        """Answer a curiosity question during a quiz session, using web search + notes."""
        try:
            notes_block = (
                f"\nRelevant study notes (use if applicable):\n{notes_context[:2000]}\n"
            ) if notes_context else ""

            system = (
                f"You are {tutor_name}, an educational tutor. "
                "Answer the student's question concisely in 2-3 sentences. "
                "Use web search when the question is about a specific tool, product, or recent info. "
                "Draw from the study notes below if they are relevant."
                f"{notes_block}"
            )
            response = self.client.messages.create(
                model=self.model,
                max_tokens=350,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}],
                system=system,
                messages=[{"role": "user", "content": question}],
            )
            text_parts = [b.text for b in response.content if hasattr(b, "text") and b.text]
            return " ".join(text_parts).strip()
        except Exception as e:
            logger.warning(f"Web search aside failed: {e}")
            return ""

    # ── Topic resolution ──────────────────────────────────────────────────────

    def resolve_topic(self, topic_filter: str, available_topics: list) -> Optional[str]:
        """Fuzzy-match a topic filter to the closest available topic folder."""
        if not available_topics or not topic_filter:
            return None
        normalized_filter = topic_filter.strip().lower()
        for topic in available_topics:
            if topic.lower() == normalized_filter:
                return topic
        for topic in available_topics:
            if normalized_filter in topic.lower() or topic.lower() in normalized_filter:
                return topic
        try:
            topics_str = "\n".join(f"- {t}" for t in available_topics)
            response = self.client.messages.create(
                model=self.model,
                max_tokens=50,
                messages=[{"role": "user", "content": (
                    f'A user wants to study: "{topic_filter}"\n'
                    f"Available topics:\n{topics_str}\n\n"
                    f'Which topic best matches? Reply with ONLY the exact topic name, or "none".'
                )}],
            )
            result = llm_text(response).lower()
            for t in available_topics:
                if t.lower() == result:
                    return t
            return None
        except Exception as e:
            logger.warning(f"LLM topic resolution failed: {e}")
            return None

    # ── Upload ────────────────────────────────────────────────────────────────

    def parse_upload_topic_reply(self, user_message: str, suggested_topic: str, document_topic: str) -> dict:
        """Parse the user's reply to a 'where should I save this?' question."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=60,
                messages=[{"role": "user", "content": (
                    f'A user was asked where to save a study document.\n'
                    f'We suggested adding it to: "{suggested_topic}"\n'
                    f'The document\'s own topic name is: "{document_topic}"\n'
                    f'The user replied: "{user_message}"\n\n'
                    f'What do they want?\n'
                    f'- If they agree to use the suggested folder: reply with exactly: use_suggested\n'
                    f'- If they want a new folder without specifying a name: reply with exactly: use_document_topic\n'
                    f'- If they named a specific folder: reply with exactly: use_custom:folder-name\n'
                    f'- If they are not actually answering the save-location question, or the reply is ambiguous: reply with exactly: unclear\n'
                    f'  (lowercase-with-hyphens, no spaces)\n\n'
                    f'Reply with ONLY one of the four formats above.'
                )}],
            )
            result = llm_text(response).lower()
            if result == "use_suggested":
                return {"action": "use_suggested"}
            elif result == "use_document_topic":
                return {"action": "use_document_topic"}
            elif result == "unclear":
                return {"action": "unclear"}
            elif result.startswith("use_custom:"):
                folder = result[len("use_custom:"):].strip()
                folder = re.sub(r"[^a-z0-9\-_]", "-", folder).strip("-")
                if folder:
                    return {"action": "use_custom", "folder": folder}
            return {"action": "unclear"}
        except Exception as e:
            logger.warning(f"parse_upload_topic_reply failed: {e}")
            return {"action": "unclear"}

    # ── Session open / close (used by study_handler) ─────────────────────────

    def generate_session_opening(
        self,
        topics_str: str,
        archetype: str = "sophia",
        persona_description: str = "",
        communication_style: Optional[Dict[str, Any]] = None,
        tutor_name: str = "Sofico",
    ) -> str:
        """Generate a fresh, LLM-written session opening."""
        voice = persona_description if persona_description else self._archetype_short_voice(archetype)
        style_guidance = self._build_communication_guidance(communication_style)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=80,
                messages=[{"role": "user", "content": (
                    f"You are {tutor_name}, {voice}. "
                    f"The learner is about to study: {topics_str}. "
                    f"Write a vivid, original one or two sentence session opening in your voice. "
                    f"{style_guidance} "
                    f"No stage directions. No asterisks."
                )}],
            )
            return llm_text(response)
        except Exception as e:
            logger.warning(f"generate_session_opening failed: {e}")
            return "Let us begin."

    def generate_session_closing(
        self,
        avg_score: float,
        topics_str: str,
        archetype: str = "sophia",
        persona_description: str = "",
        communication_style: Optional[Dict[str, Any]] = None,
        tutor_name: str = "Sofico",
    ) -> str:
        """Generate a fresh, LLM-written session closing."""
        voice = persona_description if persona_description else self._archetype_short_voice(archetype)
        style_guidance = self._build_communication_guidance(communication_style)
        if avg_score >= 4:
            perf = "The learner performed excellently."
        elif avg_score >= 3:
            perf = "The learner performed well with room to grow."
        else:
            perf = "The learner found the material challenging."
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=80,
                messages=[{"role": "user", "content": (
                    f"You are {tutor_name}, {voice}. "
                    f"A study session just ended. Topics: {topics_str}. {perf} "
                    f"Write a brief, genuine closing — one or two sentences in your voice. "
                    f"{style_guidance} "
                    f"No stage directions. No asterisks."
                )}],
            )
            return llm_text(response)
        except Exception as e:
            logger.warning(f"generate_session_closing failed: {e}")
            return "Good work today."

    # ── Onboarding (used by onboarding_handler) ───────────────────────────────

    def generate_onboarding_opening(self, learner_name: str = "", is_update: bool = False) -> str:
        """Generate a warm onboarding opener."""
        if is_update and learner_name:
            ctx = f"You are catching up with {learner_name}, who wants to update their learning preferences. Ask warmly what they'd like to change."
        elif is_update:
            ctx = "You are helping a returning learner update their preferences. Open warmly and ask what they'd like to change."
        else:
            ctx = "You are meeting a new learner. Introduce yourself briefly as Sofi and ask their name. One or two sentences — warm and natural."
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=80,
                messages=[{"role": "user", "content": f"You are Sofi, a warm learning companion. {ctx} No stage directions. No asterisks."}],
            )
            return llm_text(response)
        except Exception as e:
            logger.warning(f"generate_onboarding_opening failed: {e}")
            if is_update:
                return f"Let's update your preferences{', ' + learner_name if learner_name else ''}. What would you like to change?"
            return "Welcome! I'm Sofi, your learning companion. What's your name?"

    def generate_onboarding_confirmation(self, name: str, persona_description: str = "", archetype: str = "sophia") -> str:
        """Generate a profile-saved confirmation in the learner's voice."""
        voice = persona_description if persona_description else self._archetype_short_voice(archetype)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=80,
                messages=[{"role": "user", "content": (
                    f"You are Sofi, {voice}. "
                    f"You just finished setting up {name}'s learning profile. "
                    f"Write a single brief confirmation — profile saved, invite them to say 'quiz me'. "
                    f"No stage directions. No asterisks."
                )}],
            )
            return llm_text(response)
        except Exception as e:
            logger.warning(f"generate_onboarding_confirmation failed: {e}")
            return f"Profile saved, {name}. Say *quiz me* whenever you're ready."

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _archetype_short_voice(self, archetype: str) -> str:
        voices = {
            "sophia": "a wise, philosophical mentor in the tradition of Sophia, ancient goddess of wisdom",
            "sensei": "a direct, disciplined martial arts master who values precision",
            "grandmother": "a warm, patient elder who makes learning feel safe",
            "research-mentor": "a rigorous academic mentor who treats the learner as a peer",
        }
        return voices.get(archetype, voices["sophia"])

    def _build_prompt(
        self,
        user_message: str,
        question_text: str,
        expected_answer: str,
        category: str,
        topic: str,
        user_id: str = None,
        notes_context: str = "",
        preference_overrides: Optional[Dict[str, Any]] = None,
        learner_brief_text: str = "",
    ) -> str:
        """Build the quiz grading prompt."""
        category_hints = {
            "Recall": "Grade on whether they knew the core fact. Minor typos OK.",
            "Explain": "Paraphrasing = full points if the concept is correct.",
            "Apply": "Different correct approach than the reference answer is still 5/5.",
            "Connect": "Different examples showing the relationship are still 5/5.",
        }
        category_hint = category_hints.get(category, "")

        if user_id:
            memory_context = (
                self.memory_service.get_memory_context(user_id)
                if self.memory_service else ""
            )
            sophia_prompt = self.profile_service.build_personalized_system_prompt(
                user_id=user_id,
                context="feedback",
                memory_context=memory_context,
                preference_overrides=preference_overrides,
            )
        else:
            sophia_prompt = get_system_prompt()

        notes_block = (
            f"\nSTUDY NOTES (draw on this for hints):\n{notes_context[:3000]}\n"
        ) if notes_context else ""
        learner_block = (
            f"\nLEARNER BRIEF (runtime summary):\n{learner_brief_text.strip()}\n"
        ) if learner_brief_text.strip() else ""

        return f"""{sophia_prompt}
{learner_block}

QUESTION ({category} - {topic}):
{question_text}

REFERENCE ANSWER:
{expected_answer}
{notes_block}
STUDENT SAID:
{user_message}

Classify and respond:

1. ANSWER — They attempted to answer (including "I don't know"):
   - Grade 0-5. {category_hint}
   - "I don't know" / "no idea" = ANSWER score 0
   - Simple acknowledgments ("ok", "yes", "got it") = FOLLOWUP
   - Give specific feedback on what was right/wrong.

2. SKIP — They want to skip ("skip", "next", "pass")

3. END — They want to stop ("end", "stop", "quit", "done")

4. FOLLOWUP — They want a hint. Give a real hint, end with "Give it a try!"

5. ASIDE — A genuine curiosity question unrelated to answering. Answer in 2-3 sentences, end with "Now — back to our question."

JSON only:
{{"intent": "answer|skip|end|followup|aside", "score": null or 0-5, "response": "your text"}}"""

    def _build_communication_guidance(self, communication_style: Optional[Dict[str, Any]] = None) -> str:
        """Lightweight style instructions for small one-off prompts."""
        if not communication_style:
            return ""

        guidance = []
        verbosity = communication_style.get("verbosity", "concise")
        theatricality = communication_style.get("theatricality", "subtle")
        humor_style = communication_style.get("humor_style", "light")

        if verbosity == "concise":
            guidance.append("Keep it compact and direct.")
        elif verbosity == "chatty":
            guidance.append("A slightly more expansive conversational tone is welcome.")

        if theatricality == "subtle":
            guidance.append("Keep the persona grounded rather than dramatic.")
        elif theatricality == "vivid":
            guidance.append("Let the persona show more boldly while staying clear.")

        if humor_style == "none":
            guidance.append("Do not joke.")
        elif humor_style == "playful":
            guidance.append("A light playful touch is welcome if it fits naturally.")

        return " ".join(guidance).strip()

    def _parse_response(self, text: str) -> Dict[str, Any]:
        """Parse quiz grading JSON response."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            inner, in_block = [], False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    inner.append(line)
            text = "\n".join(inner)

        if not text.startswith("{"):
            match = re.search(r'\{[^{}]*"intent"[^{}]*\}', text, re.DOTALL)
            if match:
                text = match.group(0)
            else:
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    text = match.group(0)

        try:
            result = json.loads(text)
            intent = result.get("intent", "answer").lower()
            if intent not in ["answer", "skip", "end", "followup", "aside", "help"]:
                intent = "answer"
            if intent == "help":
                intent = "followup"
            score = result.get("score")
            if score is not None:
                score = max(0, min(5, int(score)))
            return {"intent": intent, "score": score, "response": result.get("response", ""), "error": False}
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse quiz response: {e}. Raw: {text[:200]}")
            text_lower = text.lower()
            if "skip" in text_lower:
                return {"intent": "skip", "score": None, "response": "Skipping...", "error": False}
            elif "end" in text_lower or "stop" in text_lower:
                return {"intent": "end", "score": None, "response": "Ending session...", "error": False}
            else:
                numbers = re.findall(r'\b([0-5])\b', text)
                score = int(numbers[0]) if numbers else 3
                return {"intent": "answer", "score": score, "response": text[:300], "error": False}

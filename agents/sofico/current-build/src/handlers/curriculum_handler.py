"""
Curriculum Handler
LLM-driven personalised course creation.

Flow:
  1. clarify  — Sofi asks 2-3 questions to understand what the learner wants
  2. approve  — Sofi proposes a lesson outline; learner approves or adjusts
  3. building — Sofi researches and builds lessons 1 & 2
  4. active   — Curriculum running; next lesson built in background after each completion
"""

import json
import logging
import os
import re
import threading
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional

import anthropic
import yaml

from llm_utils import MODEL_DEFAULT, llm_text
from orchestrator.artifact_store import ArtifactStore
from orchestrator.models import StudyArtifactType

logger = logging.getLogger(__name__)

CURRICULUM_STATE_MAX_AGE_HOURS = 2


def _final_synthesis_text(content) -> str:
    """Return only the text emitted after the last tool call.

    Web search interleaves Claude's planning narration with tool_use and
    tool_result blocks. The user-facing answer is the text after the final
    tool result; earlier text blocks are chain-of-thought that must not leak.
    """
    last_tool_idx = -1
    for idx, block in enumerate(content):
        block_type = getattr(block, "type", "")
        if block_type in {"server_tool_use", "web_search_tool_result", "tool_use", "tool_result"}:
            last_tool_idx = idx

    tail = content[last_tool_idx + 1:] if last_tool_idx >= 0 else content
    return "\n\n".join(
        block.text for block in tail if hasattr(block, "text") and block.text
    ).strip()


CLARIFY_SYSTEM_PROMPT = """You are Sofi, a warm and curious learning companion. A learner has asked you to help them build a personalised curriculum on a subject.

Your goal is to understand exactly what they need through a natural, brief conversation. Discover:
1. Their **current level** with this subject (complete beginner / some experience / intermediate / advanced)
2. Their **goal** — what do they want to be able to do at the end? (understand basics, build something, pass an exam, professional use, etc.)
3. **Time available** — roughly how many hours per week can they dedicate?
4. Any **specific angle or context** — e.g. "Python for web scraping", "Spanish for travel", "ML for finance"
5. **Deadline or timeline** — optional, but useful if they have one

Guidelines:
- Ask 1-2 questions at a time, not all at once
- Be warm and curious, not clinical
- If they give a vague answer, gently explore it
- Keep responses short: 2-3 sentences
- Once you have confident answers to all 5 areas, end your message with this exact marker:

CURRICULUM_CLARIFIED:{"level":"...","goal":"...","hours_per_week":N,"angle":"...","timeline":"..."}

Use null for timeline if not mentioned. hours_per_week should be a number (guess reasonably if vague).
Do not output CURRICULUM_CLARIFIED until you genuinely have confident answers."""


class CurriculumHandler:
    """
    Manages curriculum creation and progression.
    active_curricula: user_id → {phase, history, subject, clarifications, curriculum_id}
    """

    LESSONS_AHEAD = 2  # Always keep this many lessons pre-built

    def __init__(self, data_service, session_response_service, profile_service, artifact_store=None):
        self.data_service = data_service
        self.response_service = session_response_service
        self.profile_service = profile_service
        self.artifact_store = artifact_store or ArtifactStore()
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = MODEL_DEFAULT
        self.active_curricula: Dict[str, Dict[str, Any]] = {}
        self._state_notices: Dict[str, str] = {}
        self._curricula_lock = threading.Lock()

        # Expose last completed topic for slack_bot lesson-completion hook
        self.last_completed_topics: Dict[str, str] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def is_active(self, user_id: str) -> bool:
        with self._curricula_lock:
            in_memory = user_id in self.active_curricula
        if in_memory:
            if self._is_state_stale(user_id, self.active_curricula[user_id]) or not self._is_state_valid(user_id, self.active_curricula[user_id]):
                self._set_state_notice(user_id)
                self._clear_state(user_id)
                return False
            return True
        state = self.data_service.load_curriculum_state(user_id)
        if state and state.get("phase"):
            if self._is_state_stale(user_id, state) or not self._is_state_valid(user_id, state):
                self._set_state_notice(user_id)
                self._clear_state(user_id)
                return False
            self.active_curricula[user_id] = state
            return True
        return False

    def start(self, user_id: str, subject: str, say, opening: str = None):
        """Begin clarification phase for a new curriculum request.

        If opening is provided (e.g. Sofi's acknowledgment from get_sofi_response),
        use it directly to avoid sending two messages.
        """
        if not opening:
            opening = (
                f"A curriculum on *{subject}* — wonderful. "
                f"Before I start researching, let me ask a couple of things so I can tailor this properly.\n\n"
                f"What's your current level with {subject}? And what do you ultimately want to be able to do with it?"
            )

        session = {
            "phase": "clarify",
            "subject": subject,
            "history": [{"role": "assistant", "content": opening}],
            "clarifications": {},
            "curriculum_id": None,
            "plan": None,
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.active_curricula[user_id] = session
        self._save_state(user_id)
        say(opening)

    def take_state_notice(self, user_id: str) -> str:
        """Return and clear any stale-state notice for the router."""
        return self._state_notices.pop(user_id, "")

    def handle(self, user_id: str, text: str, say):
        """Route to the correct phase handler."""
        session = self.active_curricula.get(user_id)
        if not session:
            return None

        phase = session.get("phase")
        if phase == "clarify":
            self._handle_clarify(user_id, text, say)
            return None
        elif phase == "approve":
            self._handle_approve(user_id, text, say)
            return None
        elif phase == "active":
            return self._handle_active(user_id, text, say)
        return None

    def on_lesson_complete(self, user_id: str, completed_topic_slug: str, say):
        """
        Called by slack_bot after a study or explanation session ends.
        If the completed topic is the current curriculum lesson, advance and build next.
        """
        curriculum_id = self.data_service.get_active_curriculum_id(user_id)
        if not curriculum_id:
            return

        plan = self.data_service.load_curriculum_plan(user_id, curriculum_id)
        if not plan:
            return

        current_idx = plan.get("current_lesson", 0)
        lessons = plan.get("lessons", [])

        if current_idx >= len(lessons):
            return

        current_lesson = lessons[current_idx]
        if current_lesson.get("topic_slug") != completed_topic_slug:
            return

        # Advance
        lessons[current_idx]["status"] = "complete"
        next_idx = current_idx + 1
        plan["current_lesson"] = next_idx

        if next_idx >= len(lessons):
            plan["status"] = "complete"
            self.data_service.save_curriculum_plan(user_id, curriculum_id, plan)
            say(f"*You've completed the full curriculum!* 🎓 Every lesson is done. Say *show progress* to see your mastery.")
            self.data_service.clear_curriculum_state(user_id)
            self.active_curricula.pop(user_id, None)
            return

        self.data_service.save_curriculum_plan(user_id, curriculum_id, plan)

        # Announce next lesson
        next_lesson = lessons[next_idx]
        if next_lesson.get("built"):
            say(
                f"*Lesson {current_idx + 1} complete!*\n\n"
                f"Next up: *Lesson {next_idx + 1} — {next_lesson['title']}*\n"
                f"Say *quiz me* or *explain it* whenever you're ready."
            )
        else:
            say(f"*Lesson {current_idx + 1} complete!* I'm preparing lesson {next_idx + 1} — give me a moment...")
            threading.Thread(
                target=self._build_lesson_thread,
                args=(user_id, curriculum_id, next_idx, say, next_lesson["title"]),
                daemon=True
            ).start()

        # Pre-build the lesson after next (buffer)
        buffer_idx = next_idx + 1
        if buffer_idx < len(lessons) and not lessons[buffer_idx].get("built"):
            threading.Thread(
                target=self._build_lesson_thread,
                args=(user_id, curriculum_id, buffer_idx, None, None),  # silent
                daemon=True
            ).start()

    # ── Phase handlers ────────────────────────────────────────────────────────

    def _handle_clarify(self, user_id: str, text: str, say):
        session = self.active_curricula[user_id]
        history = session["history"]

        text_lower = text.strip().lower()
        if any(phrase in text_lower for phrase in {"cancel curriculum", "stop curriculum", "cancel plan", "stop plan"}):
            self._cancel_curriculum(user_id, say)
            return
        if self._is_stuck(session) and any(phrase in text_lower for phrase in {"continue", "keep going"}):
            say("All right. We’ll keep shaping the plan together.")
            return

        history.append({"role": "user", "content": text})

        # Inject known context so the LLM never asks for info it already has
        subject = session.get("subject", "")
        learner_name = ""
        try:
            profile = self.profile_service.load_profile(user_id)
            learner_name = profile.get("metadata", {}).get("learner_name", "")
        except Exception:
            pass
        context_block = ""
        if subject:
            context_block += f"\n\nThe learner's subject is already known: **{subject}**. Do NOT ask what they want to learn — you already know."
        if learner_name:
            context_block += f"\nThe learner's name is **{learner_name}**. Do NOT ask for their name."
        clarify_system = CLARIFY_SYSTEM_PROMPT + context_block

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=400,
                system=clarify_system,
                messages=history,
            )
            reply = llm_text(response)
        except Exception as e:
            logger.error(f"Clarify LLM error for {user_id}: {e}")
            say("Something went wrong — please try again.")
            return

        parsed = self._extract_marker_json(reply, "CURRICULUM_CLARIFIED")
        if parsed:
            conversational, clarifications = parsed
            if conversational:
                say(conversational)
            try:
                session["clarifications"] = clarifications
                history.append({"role": "assistant", "content": conversational or reply})
                if len(history) > 20:
                    session["history"] = history[-20:]
                self._save_state(user_id)
                self._research_and_propose_plan(user_id, say)
            except KeyError as e:
                logger.error(f"Failed to parse clarifications for {user_id}: {e}")
                history.append({"role": "assistant", "content": reply})
                self._save_state(user_id)
                say("Let me ask a couple more things...")
        else:
            history.append({"role": "assistant", "content": reply})
            if len(history) > 20:
                session["history"] = history[-20:]
            self._save_state(user_id)
            if self._is_stuck(session):
                say(
                    f"{reply}\n\n"
                    f"_If this planning chat is getting stuck, you can say `cancel curriculum` to exit for now._"
                )
            else:
                say(reply)

    def _research_and_propose_plan(self, user_id: str, say):
        """Research the subject and propose a lesson outline."""
        session = self.active_curricula[user_id]
        subject = session["subject"]
        clarifications = session["clarifications"]

        say(
            f"_Researching {subject} now — I'll look at what the best sources recommend for your level and goal. "
            f"This takes about 30 seconds..._"
        )

        try:
            outline = self._build_outline_with_research(subject, clarifications)
        except Exception as e:
            logger.error(f"Outline research failed for {user_id}: {e}")
            say("I had trouble researching that topic. Please try again.")
            del self.active_curricula[user_id]
            self.data_service.clear_curriculum_state(user_id)
            return

        # Format the outline for the learner
        clarify = clarifications
        timeline_note = f" (timeline: {clarify.get('timeline')})" if clarify.get("timeline") else ""
        hours = clarify.get("hours_per_week", "?")

        lines = [
            f"Here's the curriculum I've put together for *{subject}*{timeline_note}:",
            f"_{clarify.get('goal', '')} · {hours}h/week_\n",
        ]
        for lesson in outline:
            lines.append(f"*Lesson {lesson['index'] + 1}* — {lesson['title']}\n_{lesson['description']}_")

        lines.append(
            "\nDoes this look right? You can say *looks good* to start, or ask me to adjust anything "
            "(e.g. 'add a lesson on X', 'fewer lessons', 'make it more advanced')."
        )

        proposal = "\n\n".join(lines)
        say(proposal)

        session["phase"] = "approve"
        session["history"] = [{"role": "assistant", "content": proposal}]
        session["plan"] = outline
        self._save_state(user_id)

    def _handle_approve(self, user_id: str, text: str, say):
        session = self.active_curricula[user_id]
        outline = session["plan"]
        history = session["history"]

        text_lower = text.lower().strip()
        if any(phrase in text_lower for phrase in {"cancel curriculum", "stop curriculum", "cancel plan", "stop plan"}):
            self._cancel_curriculum(user_id, say)
            return

        history.append({"role": "user", "content": text})

        # Simple approval detection — let LLM interpret
        approval_words = {"yes", "looks good", "good", "perfect", "great", "ok", "okay",
                          "start", "let's go", "go ahead", "sounds good", "approved", "build it"}

        is_approved = any(w in text_lower for w in approval_words)

        if is_approved:
            self._execute_approved_plan(user_id, outline, say)
        else:
            # Ask LLM to interpret and adjust the outline
            self._handle_outline_adjustment(user_id, text, say)

    def _handle_outline_adjustment(self, user_id: str, text: str, say):
        session = self.active_curricula[user_id]
        outline = session["plan"]
        subject = session["subject"]

        outline_text = "\n".join(
            f"Lesson {l['index'] + 1}: {l['title']} — {l['description']}"
            for l in outline
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=600,
                messages=[{"role": "user", "content": (
                    f"A learner is reviewing a curriculum outline for '{subject}' and has feedback.\n\n"
                    f"Current outline:\n{outline_text}\n\n"
                    f"Learner says: \"{text}\"\n\n"
                    f"If they want adjustments, update the outline and reply with the revised version, "
                    f"ending with OUTLINE_UPDATED:[{{\"index\":0,\"title\":\"...\",\"description\":\"...\"}},...]\n"
                    f"If they are approving or satisfied, just confirm and end with OUTLINE_APPROVED.\n"
                    f"Reply naturally in Sofi's voice."
                )}]
            )
            reply = llm_text(response)
        except Exception as e:
            logger.error(f"Outline adjustment error for {user_id}: {e}")
            say("I had trouble with that — could you rephrase?")
            return

        if self._has_marker(reply, "OUTLINE_APPROVED"):
            say(reply.split("OUTLINE_APPROVED")[0].strip() or "Great, let's build it!")
            self._execute_approved_plan(user_id, outline, say)
        else:
            parsed = self._extract_marker_json(reply, "OUTLINE_UPDATED")
            if parsed:
                conversational, new_outline = parsed
                if conversational:
                    say(conversational)
                else:
                    say("I’ve updated the outline.")
                try:
                    session["plan"] = new_outline
                    self._save_state(user_id)
                except Exception as e:
                    logger.error(f"Could not save updated outline for {user_id}: {e}")
                    say("I revised it, but had trouble saving the new outline. Could you ask again?")
            else:
                say(reply)
                session["history"].append({"role": "assistant", "content": reply})
                self._save_state(user_id)

    def _execute_approved_plan(self, user_id: str, outline: list, say):
        """Learner approved — save plan, build first two lessons."""
        session = self.active_curricula[user_id]
        subject = session["subject"]
        clarifications = session["clarifications"]

        curriculum_id = re.sub(r'[^a-z0-9]+', '-', subject.lower()).strip('-')
        curriculum_id = f"{curriculum_id}-{date.today().isoformat()}"
        session["curriculum_id"] = curriculum_id

        plan = {
            "id": curriculum_id,
            "title": subject,
            "created": date.today().isoformat(),
            "status": "active",
            "current_lesson": 0,
            "lessons_built": [],
            "clarifications": clarifications,
            "lessons": [
                {
                    "index": l["index"],
                    "title": l["title"],
                    "description": l["description"],
                    "topic_slug": self._make_topic_slug(curriculum_id, l["index"], l["title"]),
                    "built": False,
                    "status": "upcoming",
                }
                for l in outline
            ],
        }
        plan["lessons"][0]["status"] = "current"

        self.data_service.save_curriculum_plan(user_id, curriculum_id, plan)
        self._register_course_plan_artifact(user_id, curriculum_id, subject, plan)
        session["phase"] = "active"
        session["plan"] = plan
        self._save_state(user_id)

        say(
            f"*Perfect.* I'll build your first two lessons now — this takes about a minute.\n"
            f"_Researching Lesson 1: {plan['lessons'][0]['title']}..._"
        )

        # Build lessons 0 and 1 synchronously (user is waiting)
        self._build_lesson_sync(user_id, curriculum_id, 0)
        if len(plan["lessons"]) > 1:
            say(f"_Researching Lesson 2: {plan['lessons'][1]['title']}..._")
            self._build_lesson_sync(user_id, curriculum_id, 1)

        # Reload plan to get updated built status
        plan = self.data_service.load_curriculum_plan(user_id, curriculum_id)
        built_count = len(plan.get("lessons_built", []))
        first = plan["lessons"][0]

        say(
            f"*Your curriculum is ready!* {built_count} lessons prepared.\n\n"
            f"*Start with Lesson 1 — {first['title']}*\n"
            f"Say *explain it* to walk through it, or *quiz me* to jump straight into questions."
        )

    def _handle_active(self, user_id: str, text: str, say):
        """Curriculum is active — help the learner navigate to their current lesson."""
        curriculum_id = self.data_service.get_active_curriculum_id(user_id)
        if not curriculum_id:
            self._clear_state(user_id)
            say("Your active curriculum is no longer running. We can start a new one whenever you want.")
            return None

        plan = self.data_service.load_curriculum_plan(user_id, curriculum_id)
        current_idx = plan.get("current_lesson", 0)
        lessons = plan.get("lessons", [])

        if current_idx < len(lessons):
            lesson = lessons[current_idx]
            text_lower = text.strip().lower()
            if self._is_explain_intent(text_lower):
                return {"action": "explain", "topic": lesson["topic_slug"]}

            if self._is_quiz_intent(text_lower):
                return {"action": "quiz", "topic": lesson["topic_slug"]}

            if self._is_lesson_question(text):
                say(
                    f"*Lesson {current_idx + 1} — {lesson['title']}*\n"
                    f"{lesson['description']}\n\n"
                    f"I can walk you through it step by step, or quiz you on it. Which do you want?"
                )
                return None

            if self._is_ambiguous_lesson_nudge(text_lower):
                say(
                    f"You’re on *Lesson {current_idx + 1} — {lesson['title']}*.\n"
                    f"Do you want me to *explain it*, *quiz you on it*, or do something else?"
                )
                return None

            say(
                f"You’re on *Lesson {current_idx + 1} — {lesson['title']}*.\n"
                f"I can explain it step by step or quiz you on it. Which do you want?"
            )
        return None

    # ── Lesson building ───────────────────────────────────────────────────────

    def _build_lesson_sync(self, user_id: str, curriculum_id: str, lesson_index: int):
        """Build a lesson synchronously. Logs errors but doesn't crash."""
        try:
            plan = self.data_service.load_curriculum_plan(user_id, curriculum_id)
            lessons = plan.get("lessons", [])
            if lesson_index >= len(lessons):
                return

            lesson = lessons[lesson_index]
            subject = plan.get("title", "")
            clarifications = plan.get("clarifications", {})
            level = clarifications.get("level", "intermediate")

            # Research the lesson content
            research_text = self._research_lesson_content(
                lesson["title"], lesson["description"], subject, level
            )

            # Parse into study document + cards
            from services.document_parser_service import DocumentParserService
            parser = DocumentParserService()
            result = parser.parse_document(
                content=research_text,
                user_id=user_id,
                topic_hint=lesson["topic_slug"],
                data_service=self.data_service,
            )

            # Save
            topic_slug = lesson["topic_slug"]
            doc_name = topic_slug
            self.data_service.save_study_document(user_id, topic_slug, doc_name, result["study_document"])

            # Update topic index
            index_data = self.data_service.get_topic_index(user_id, topic_slug) or {
                "topic": topic_slug,
                "last_updated": date.today().isoformat(),
                "questions": [],
            }
            existing_ids = {q["id"] for q in index_data.get("questions", [])}
            for q in result.get("questions", []):
                if q["id"] not in existing_ids:
                    index_data["questions"].append(q)
            index_data["last_updated"] = date.today().isoformat()
            self.data_service.update_topic_index(user_id, topic_slug, index_data)

            # Mark built in plan
            lessons[lesson_index]["built"] = True
            lessons[lesson_index]["status"] = "current" if lesson_index == plan.get("current_lesson", 0) else "upcoming"
            built = plan.get("lessons_built", [])
            if lesson_index not in built:
                built.append(lesson_index)
            plan["lessons_built"] = built
            plan["lessons"] = lessons
            self.data_service.save_curriculum_plan(user_id, curriculum_id, plan)
            self._register_lesson_artifacts(user_id, curriculum_id, lesson, result)

            logger.info(f"Built lesson {lesson_index} ({lesson['title']}) for {user_id}")

        except Exception as e:
            logger.error(f"Failed to build lesson {lesson_index} for {user_id}: {e}")

    def _register_course_plan_artifact(self, user_id: str, curriculum_id: str, subject: str, plan: Dict[str, Any]):
        """Register the saved curriculum as a first-class artifact."""
        self.artifact_store.add_artifact(
            user_id=user_id,
            artifact_type=StudyArtifactType.COURSE_PLAN,
            title=subject,
            topic=subject,
            linked_plan_id=curriculum_id,
            metadata={
                "lesson_count": len(plan.get("lessons", [])),
                "created": plan.get("created"),
                "status": plan.get("status"),
            },
        )

    def _register_lesson_artifacts(
        self,
        user_id: str,
        curriculum_id: str,
        lesson: Dict[str, Any],
        result: Dict[str, Any],
    ):
        """Register lesson material and its linked question set."""
        topic_slug = lesson["topic_slug"]
        source_path = f"{topic_slug}/{topic_slug}.md"
        lesson_artifact = self.artifact_store.add_artifact(
            user_id=user_id,
            artifact_type=StudyArtifactType.LESSON_MATERIAL,
            title=lesson["title"],
            topic=topic_slug,
            source_path=source_path,
            linked_plan_id=curriculum_id,
            metadata={
                "description": lesson.get("description", ""),
                "question_count": len(result.get("questions", [])),
            },
        )
        self.artifact_store.add_artifact(
            user_id=user_id,
            artifact_type=StudyArtifactType.QUESTION_SET,
            title=f"{lesson['title']} questions",
            topic=topic_slug,
            source_path=source_path,
            source_artifact_id=lesson_artifact.artifact_id,
            linked_plan_id=curriculum_id,
            metadata={
                "question_count": len(result.get("questions", [])),
            },
        )

    def _build_lesson_thread(self, user_id: str, curriculum_id: str, lesson_index: int,
                              say, lesson_title: Optional[str]):
        """Background thread wrapper for lesson building."""
        self._build_lesson_sync(user_id, curriculum_id, lesson_index)
        if say and lesson_title:
            try:
                say(f"*Lesson {lesson_index + 1} — {lesson_title}* is ready. Say *quiz me* or *explain it* to begin.")
            except Exception as e:
                logger.warning(f"Could not send lesson-ready message: {e}")

    def _research_lesson_content(self, title: str, description: str, subject: str, level: str) -> str:
        """Use web search to research a lesson topic. Returns raw synthesised text."""
        prompt = (
            f"You are researching content for a lesson titled '{title}' within a course on '{subject}'.\n"
            f"Lesson description: {description}\n"
            f"Target learner level: {level}\n\n"
            f"Research this topic thoroughly using web search. Then write comprehensive lesson notes (600-900 words) covering:\n"
            f"- Core concepts and definitions\n"
            f"- Key principles and how they work\n"
            f"- Practical examples\n"
            f"- Common pitfalls or misconceptions\n"
            f"- How this connects to what comes before and after in the course\n\n"
            f"Write in clear, educational prose. Use markdown headers. Be specific and accurate."
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
            messages=[{"role": "user", "content": prompt}],
        )

        return _final_synthesis_text(response.content)

    def _build_outline_with_research(self, subject: str, clarifications: dict) -> list:
        """Research and produce a structured lesson outline (6-12 lessons)."""
        level = clarifications.get("level", "beginner")
        goal = clarifications.get("goal", "understand the basics")
        hours = clarifications.get("hours_per_week", 3)
        angle = clarifications.get("angle") or ""
        timeline = clarifications.get("timeline") or ""

        # Estimate lesson count from available time
        # Assume ~2h per lesson; total hours = hours/week * weeks
        weeks_hint = ""
        if timeline:
            weeks_hint = f"Timeline: {timeline}. "

        prompt = (
            f"Design a curriculum for learning '{subject}'.\n"
            f"Learner level: {level}\n"
            f"Goal: {goal}\n"
            f"Hours per week: {hours}\n"
            f"{'Specific angle: ' + angle if angle else ''}\n"
            f"{weeks_hint}\n"
            f"Use web search to research what the best structured approach to learning {subject} is "
            f"at this level. Look at course syllabi, expert recommendations, and learning resources.\n\n"
            f"Then design a curriculum of 6-12 lessons that:\n"
            f"- Builds logically from foundational to advanced\n"
            f"- Is scoped appropriately for the learner's level and goal\n"
            f"- Each lesson is roughly 1-2 hours of focused study\n\n"
            f"Output ONLY a JSON array (no other text):\n"
            f'[{{"index":0,"title":"Lesson Title","description":"One sentence describing what is covered"}},...]\n'
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            thinking={"type": "enabled", "budget_tokens": 4000},
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
            messages=[{"role": "user", "content": prompt}],
        )

        raw = _final_synthesis_text(response.content)

        # Extract JSON array
        match = re.search(r'\[[\s\S]*\]', raw)
        if match:
            return json.loads(match.group(0))

        raise ValueError(f"Could not parse outline from response: {raw[:300]}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_topic_slug(self, curriculum_id: str, index: int, title: str) -> str:
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        return f"{curriculum_id}-lesson-{index + 1:02d}-{slug}"[:80]

    def _is_explain_intent(self, text_lower: str) -> bool:
        explain_phrases = (
            "explain",
            "walk me through",
            "teach me",
            "go through the lesson",
            "start the lesson",
            "give me the lesson",
            "continue the lesson",
        )
        return any(phrase in text_lower for phrase in explain_phrases)

    def _is_quiz_intent(self, text_lower: str) -> bool:
        quiz_phrases = (
            "quiz me",
            "test me",
            "ask me questions",
            "start questions",
            "give me questions",
            "practice questions",
        )
        return any(phrase in text_lower for phrase in quiz_phrases)

    def _is_lesson_question(self, text: str) -> bool:
        lowered = text.strip().lower()
        question_starters = ("what", "why", "how", "which", "when", "where", "can", "could", "should", "is", "are")
        return lowered.endswith("?") or lowered.startswith(question_starters)

    def _is_ambiguous_lesson_nudge(self, text_lower: str) -> bool:
        return text_lower in {
            "continue",
            "go on",
            "keep going",
            "carry on",
            "ok",
            "okay",
            "next",
            "start",
            "let's go",
            "lets go",
            "ready",
        }

    def _save_state(self, user_id: str):
        try:
            state = self.active_curricula.get(user_id, {})
            if state:
                state["updated_at"] = datetime.now().isoformat()
            # Don't persist full plan in state if it's already in plan.yaml
            state_to_save = {k: v for k, v in state.items() if k != "plan"}
            if len(state.get("history", [])) > 20:
                state_to_save["history"] = state["history"][-20:]
            self.data_service.save_curriculum_state(user_id, state_to_save)
        except Exception as e:
            logger.warning(f"Could not save curriculum state for {user_id}: {e}")

    def _cancel_curriculum(self, user_id: str, say):
        """Exit an in-progress curriculum conversation cleanly."""
        self._clear_state(user_id)
        say("Okay. I’ve stopped the curriculum flow for now. We can start fresh whenever you want.")

    def _is_stuck(self, session: Dict[str, Any]) -> bool:
        """Return True when the clarification chat has gone on long enough to need an escape hatch."""
        user_turns = sum(1 for item in session.get("history", []) if item.get("role") == "user")
        return user_turns >= 5

    def _has_marker(self, text: str, marker: str) -> bool:
        """Detect marker names even if the model wraps them in punctuation or code fences."""
        return bool(re.search(rf"{re.escape(marker)}\b", text))

    def _extract_marker_json(self, text: str, marker: str):
        """Find marker anywhere in the response and decode the JSON payload after it."""
        match = re.search(rf"{re.escape(marker)}\s*:\s*", text)
        if not match:
            return None

        conversational = text[:match.start()].strip()
        payload = text[match.end():].strip()
        parsed = self._extract_json_value(payload)
        if parsed is None:
            logger.warning(f"Could not parse {marker} payload. Raw: {payload[:200]}")
            return None
        return conversational, parsed

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

    def _set_state_notice(self, user_id: str):
        self._state_notices[user_id] = (
            "Your old curriculum setup had gone stale, so I cleared it. Want to continue the lesson or start fresh?"
        )

    def _clear_state(self, user_id: str):
        with self._curricula_lock:
            self.active_curricula.pop(user_id, None)
        self.data_service.clear_curriculum_state(user_id)

    def _is_state_stale(self, user_id: str, session: Dict[str, Any]) -> bool:
        updated_at = session.get("updated_at") or session.get("started_at")
        if not updated_at:
            return False
        try:
            timestamp = datetime.fromisoformat(updated_at)
        except ValueError:
            logger.warning(f"Invalid curriculum timestamp for {user_id}: {updated_at}")
            return True
        return datetime.now() - timestamp > timedelta(hours=CURRICULUM_STATE_MAX_AGE_HOURS)

    def _is_state_valid(self, user_id: str, session: Dict[str, Any]) -> bool:
        phase = session.get("phase")
        if phase not in {"clarify", "approve", "active"}:
            return False

        subject = (session.get("subject") or "").strip()
        if phase in {"clarify", "approve"} and not subject:
            return False

        if phase == "active":
            curriculum_id = session.get("curriculum_id") or self.data_service.get_active_curriculum_id(user_id)
            if not curriculum_id:
                return False
            plan = self.data_service.load_curriculum_plan(user_id, curriculum_id)
            lessons = plan.get("lessons", [])
            current_idx = plan.get("current_lesson", 0)
            if not plan or plan.get("status") not in {"active", "complete"}:
                return False
            if not lessons or current_idx >= len(lessons):
                return False
        return True

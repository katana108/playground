"""
Study Handler
Manages quiz sessions with spaced repetition and interleaving
"""

import json
import logging
import copy
import threading
from datetime import date
from pathlib import Path
from typing import List, Dict, Any, Optional
import random

from llm_utils import llm_text


logger = logging.getLogger(__name__)


class StudyHandler:
    """Handles study/quiz sessions"""

    def __init__(self, gitlab_service, sm2_service, session_response_service):
        self.gitlab = gitlab_service
        self.sm2 = sm2_service
        self.response_service = session_response_service
        self.active_sessions = {}  # user_id -> session state
        self.last_completed_topic = {}  # user_id -> topic_slug of most recently completed session
        self.last_completed_sessions = {}  # user_id -> completed session snapshot
        self._sessions_lock = threading.Lock()
        self.personality = self._load_personality()

    def _load_personality(self) -> Dict[str, Any]:
        """Load Sofi's personality configuration"""
        try:
            config_path = Path(__file__).parent.parent / "config" / "personality.json"
            with open(config_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load personality: {e}")
            return {"responses": {}}

    def _resolve_voice_settings(
        self,
        user: str,
        learner_brief: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, Optional[str], Dict[str, Any], str]:
        """Resolve persona and communication settings, preferring the learner brief."""
        brief = learner_brief or {}
        style_brief = brief.get("style", {}) or {}
        tutor_name = style_brief.get("tutor_name") or "Sofico"
        try:
            profile = self.response_service.profile_service.load_profile(user)
            archetype = style_brief.get("archetype") or profile.get("character", {}).get("archetype", "sophia")
            persona_description = style_brief.get("persona_description")
            if persona_description is None:
                persona_description = profile.get("character", {}).get("persona_description")
            communication_style = self.response_service.profile_service.get_communication_style(user)
        except Exception:
            profile = {}
            archetype = style_brief.get("archetype") or "sophia"
            persona_description = style_brief.get("persona_description")
            communication_style = {}

        communication_style = {
            **communication_style,
            **((style_brief.get("communication_style", {}) or {})),
        }
        return archetype, persona_description, communication_style, tutor_name

    def _format_learner_brief_text(self, learner_brief: Optional[Dict[str, Any]]) -> str:
        """Render a compact learner brief for grading prompts."""
        if not learner_brief:
            return ""

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

        return "\n".join(parts)

    def handle(
        self,
        event,
        say,
        preference_overrides: Optional[Dict[str, Any]] = None,
        learner_brief: Optional[Dict[str, Any]] = None,
    ):
        """Handle study request"""
        user = event.get("user")
        text = event.get("text", "")

        with self._sessions_lock:
            has_session = user in self.active_sessions

        if has_session:
            if learner_brief is not None:
                self.active_sessions[user]["learner_brief"] = copy.deepcopy(learner_brief)
            self._handle_message(user, text, say, preference_overrides=preference_overrides)
        else:
            self._start_session(
                user,
                text,
                say,
                preference_overrides=preference_overrides,
                learner_brief=learner_brief,
            )

    def _extract_topic_filter(self, text: str) -> str:
        """Extract topic filter from user request like 'quiz me on portuguese'"""
        import re
        text_lower = text.lower().strip()

        # Strip common leading phrases first, so patterns match more naturally
        # e.g. "can we do just portuguese today?" → "just portuguese today?"
        leading_phrases = [
            r"^can we (do )?", r"^let'?s (do )?", r"^i want to (do )?",
            r"^i'?d like to (do )?", r"^maybe ", r"^can you "
        ]
        for phrase in leading_phrases:
            text_lower = re.sub(phrase, "", text_lower).strip()

        # Now check for patterns that indicate a topic
        patterns = [
            "quiz me on ", "test me on ", "quiz on ",
            "questions on ", "questions about ",
            "just ", "only ", "focus on ", "do ",
            "study ", "practice ",
        ]

        for pattern in patterns:
            if text_lower.startswith(pattern):
                topic = text_lower[len(pattern):].strip()
                # Clean up common trailing words
                for suffix in [" please", " now", " today", " only", " questions"]:
                    if topic.endswith(suffix):
                        topic = topic[:-len(suffix)].strip()
                # Clean up common leading qualifiers
                for qualifier in ["only ", "just ", "the ", "some "]:
                    if topic.startswith(qualifier):
                        topic = topic[len(qualifier):].strip()
                if topic and len(topic) > 1:
                    return topic

        return None

    def _extract_category_filter(self, text: str) -> str:
        """Extract a requested question category like Recall or Apply."""
        lowered = text.lower()
        category_map = {
            "recall": "Recall",
            "explain": "Explain",
            "apply": "Apply",
            "connect": "Connect",
        }
        if "question" not in lowered and "quiz" not in lowered and "test" not in lowered:
            return ""
        for token, category in category_map.items():
            if token in lowered:
                return category
        return ""

    def _start_session(
        self,
        user: str,
        text: str,
        say,
        preference_overrides: Optional[Dict[str, Any]] = None,
        learner_brief: Optional[Dict[str, Any]] = None,
    ):
        """Start a new study session"""
        # Check for topic filter
        topic_filter = self._extract_topic_filter(text)
        category_filter = self._extract_category_filter(text)

        if topic_filter:
            say(f"Looking for questions on *{topic_filter}*...")
        elif category_filter:
            say(f"Looking for *{category_filter}* questions...")
        else:
            say("Let me find your due questions...")

        try:
            # Get due questions, optionally filtered by topic
            questions = self.gitlab.get_due_questions(user, topic_filter=topic_filter)
            if category_filter:
                questions = [
                    q for q in questions
                    if str(q.get("category", "")).lower() == category_filter.lower()
                ]

            if not questions:
                if topic_filter:
                    # Try LLM fuzzy matching before giving up
                    available = self.gitlab.get_available_topics(user)
                    resolved = self.response_service.resolve_topic(topic_filter, available)
                    if resolved:
                        logger.info(f"Fuzzy resolved '{topic_filter}' → '{resolved}'")
                        topic_filter = resolved
                        questions = self.gitlab.get_due_questions(user, topic_filter=topic_filter)

                    if not questions:
                        topics_list = ", ".join(available) if available else "none found"
                        say(
                            f"No questions due for *{topic_filter}*.\n"
                            f"Available topics: {topics_list}"
                        )
                        return
                elif category_filter:
                    say(
                        f"No *{category_filter}* questions are due right now. "
                        "You can ask for another category or say `quiz me` for all due questions."
                    )
                    return
                else:
                    say(
                        "No questions due for review today! "
                        "Upload some study material or check back tomorrow."
                    )
                    return

            # Weighted random selection - lower mastery = higher probability
            session_size = 15  # TODO: Get from user config
            questions = self._weighted_random_select(questions, session_size)

            # Then interleave to mix topics
            questions = self._interleave_questions(questions)

            topics_str = ', '.join(set(q['topic'] for q in questions))

            # Load learner archetype/persona for personalized messages
            archetype, persona_description, communication_style, tutor_name = self._resolve_voice_settings(
                user,
                learner_brief=learner_brief,
            )

            if preference_overrides:
                communication_style = {
                    **communication_style,
                    **preference_overrides.get("communication", {}),
                    **preference_overrides.get("interaction_preferences", {}),
                }

            # Store session state
            self.active_sessions[user] = {
                "questions": questions,
                "current_index": 0,
                "results": [],
                "started_at": date.today().isoformat(),
                "archetype": archetype,
                "preference_overrides": preference_overrides or {},
                "communication_style": communication_style,
                "learner_brief": copy.deepcopy(learner_brief or {}),
            }

            start_msg = self.response_service.generate_session_opening(
                topics_str,
                archetype,
                persona_description=persona_description,
                communication_style=communication_style,
                tutor_name=tutor_name,
            )

            say(
                f"*Starting study session* - {len(questions)} questions\n"
                f"Topics: {topics_str}\n\n"
                f"{start_msg}\n\n"
                f"---\n"
                f"_Say `end` to stop · `customize` to change my style · `show progress` · `help`_"
            )

            self._ask_next_question(user, say)

        except Exception as e:
            logger.error(f"Error starting session: {e}", exc_info=True)
            say("Sorry, I couldn't start the session. Please try again.")

    def start_document_session(
        self,
        user: str,
        *,
        artifact_title: str,
        topic: str,
        doc_name: str,
        questions: List[Dict[str, Any]],
        say,
        preference_overrides: Optional[Dict[str, Any]] = None,
        learner_brief: Optional[Dict[str, Any]] = None,
    ):
        """Start a document-scoped review session from one exact saved paper."""
        if not questions:
            say(f"I do not see saved questions for *{artifact_title}* yet.")
            return

        prepared_questions = [copy.deepcopy(question) for question in questions]
        for question in prepared_questions:
            question.setdefault("topic", topic)
            question.setdefault("category", question.get("type", "Recall"))

        archetype, persona_description, communication_style, tutor_name = self._resolve_voice_settings(
            user,
            learner_brief=learner_brief,
        )

        if preference_overrides:
            communication_style = {
                **communication_style,
                **preference_overrides.get("communication", {}),
                **preference_overrides.get("interaction_preferences", {}),
            }

        self.active_sessions[user] = {
            "questions": prepared_questions,
            "current_index": 0,
            "results": [],
            "started_at": date.today().isoformat(),
            "archetype": archetype,
            "preference_overrides": preference_overrides or {},
            "communication_style": communication_style,
            "learner_brief": copy.deepcopy(learner_brief or {}),
            "scope_type": "document",
            "scope_label": artifact_title,
            "scope_topic": topic,
            "scope_doc_name": doc_name,
        }

        start_msg = self.response_service.generate_session_opening(
            artifact_title,
            archetype,
            persona_description=persona_description,
            communication_style=communication_style,
            tutor_name=tutor_name,
        )

        say(
            f"*Starting study session* - {len(prepared_questions)} questions\n"
            f"Document: {artifact_title}\n"
            f"Topic: {topic}\n\n"
            f"{start_msg}\n\n"
            f"---\n"
            f"_Say `end` to stop · `customize` to change my style · `show progress` · `help`_"
        )

        self._ask_next_question(user, say)

    def start_topic_corpus_session(
        self,
        user: str,
        *,
        topic: str,
        questions: List[Dict[str, Any]],
        document_titles: List[str],
        say,
        preference_overrides: Optional[Dict[str, Any]] = None,
        learner_brief: Optional[Dict[str, Any]] = None,
    ):
        """Start a topic-scoped quiz across multiple saved documents."""
        if not questions:
            say(f"I do not see ready review questions under *{topic}* yet.")
            return

        prepared_questions = [copy.deepcopy(question) for question in questions]
        for question in prepared_questions:
            question.setdefault("topic", topic)
            question.setdefault("category", question.get("type", "Recall"))

        questions = self._weighted_random_select(prepared_questions, 15)
        questions = self._interleave_questions(questions)

        archetype, persona_description, communication_style, tutor_name = self._resolve_voice_settings(
            user,
            learner_brief=learner_brief,
        )

        if preference_overrides:
            communication_style = {
                **communication_style,
                **preference_overrides.get("communication", {}),
                **preference_overrides.get("interaction_preferences", {}),
            }

        scope_label = f"{topic} papers"
        self.active_sessions[user] = {
            "questions": questions,
            "current_index": 0,
            "results": [],
            "started_at": date.today().isoformat(),
            "archetype": archetype,
            "preference_overrides": preference_overrides or {},
            "communication_style": communication_style,
            "learner_brief": copy.deepcopy(learner_brief or {}),
            "scope_type": "topic_corpus",
            "scope_label": scope_label,
            "scope_topic": topic,
            "scope_documents": list(document_titles),
        }

        start_msg = self.response_service.generate_session_opening(
            scope_label,
            archetype,
            persona_description=persona_description,
            communication_style=communication_style,
            tutor_name=tutor_name,
        )
        preview_titles = ", ".join(document_titles[:3])
        if len(document_titles) > 3:
            preview_titles += f", and {len(document_titles) - 3} more"

        say(
            f"*Starting study session* - {len(questions)} questions\n"
            f"Topic corpus: {topic}\n"
            f"Documents: {preview_titles}\n\n"
            f"{start_msg}\n\n"
            f"---\n"
            f"_Say `end` to stop · `customize` to change my style · `show progress` · `help`_"
        )

        self._ask_next_question(user, say)

    def repeat_current_question(self, user: str, say):
        """Re-ask the current question after a side conversation."""
        session = self.active_sessions.get(user)
        if not session:
            return
        idx = session["current_index"]
        questions = session["questions"]
        if idx >= len(questions):
            return
        q = questions[idx]
        total = len(questions)
        scope_label = session.get("scope_label") or q.get("topic", "")
        say(f"_Back to your quiz —_ _{idx + 1}/{total}_ — *{scope_label}*\n\n{q['text']}")

    def cancel_session(self, user: str):
        """Drop an active quiz session without sending the normal closing flow."""
        with self._sessions_lock:
            session = self.active_sessions.get(user)
            if not session:
                return
            session.pop("awaiting_self_grade", None)
            session.pop("pending_question", None)
            session.pop("pending_answer", None)
            del self.active_sessions[user]

    def take_last_completed_session(self, user: str) -> Optional[Dict[str, Any]]:
        """Return and clear the most recent completed study session snapshot."""
        session = self.last_completed_sessions.pop(user, None)
        return copy.deepcopy(session) if session else None

    def _ask_next_question(self, user: str, say):
        """Ask the next question in the session"""
        session = self.active_sessions.get(user)
        if not session:
            return

        idx = session["current_index"]
        questions = session["questions"]

        if idx >= len(questions):
            self._end_session(user, say)
            return

        q = questions[idx]
        total = len(questions)
        scope_label = session.get("scope_label") or q.get("topic", "")
        say(f"_{idx + 1}/{total}_ — *{scope_label}*\n\n{q['text']}")

    def _handle_message(
        self,
        user: str,
        message: str,
        say,
        preference_overrides: Optional[Dict[str, Any]] = None,
    ):
        """Handle any user message during a session using unified LLM service"""
        session = self.active_sessions.get(user)
        if not session:
            return

        session["preference_overrides"] = preference_overrides or {}

        # Check for self-assessment (user rating their own answer 0-5)
        message_stripped = message.strip().lower()
        if message_stripped in ["0", "1", "2", "3", "4", "5"] and session.get("awaiting_self_grade"):
            self._handle_self_grade(user, int(message_stripped), say)
            return

        # Get current question — guard before access so a corrupt index can't crash
        idx = session["current_index"]
        questions = session["questions"]
        if idx >= len(questions):
            self._end_session(user, say)
            return
        q = questions[idx]

        # Load topic notes for RAG context (lets Claude give richer hints)
        notes_context = ""
        try:
            if session.get("scope_type") == "document" and session.get("scope_topic") and session.get("scope_doc_name"):
                notes_context = self.gitlab.get_study_document_notes(
                    user,
                    session.get("scope_topic", ""),
                    session.get("scope_doc_name", ""),
                )
            if not notes_context:
                notes_context = self.gitlab.get_topic_notes(user, q.get("topic", ""))
        except Exception:
            pass

        # Process through unified LLM service
        say("Processing...")
        result = self.response_service.process_message(
            user_message=message,
            question_text=q["text"],
            expected_answer=q["answer"],
            category=q.get("category", "Recall"),
            topic=q.get("topic", "general"),
            user_id=user,
            notes_context=notes_context,
            preference_overrides=session.get("preference_overrides"),
            learner_brief_text=self._format_learner_brief_text(session.get("learner_brief")),
        )

        # Handle API error - fall back to self-assessment
        if result.get("error"):
            session["awaiting_self_grade"] = True
            session["pending_question"] = q
            session["pending_answer"] = message

            say(
                f"Sorry, {result['response']}\n\n"
                f"*Reference answer:* {q['answer']}\n\n"
                f"Please rate yourself (0-5):\n"
                f"0=blank, 1=wrong, 2=close, 3=mostly right, 4=minor gaps, 5=perfect\n\n"
                f"Or type `skip` to skip this question."
            )
            return

        # Dispatch based on intent
        intent = result["intent"]

        if intent == "skip":
            session["results"].append({"skipped": True})
            session["current_index"] += 1
            say("Skipped. Moving on...")
            self._ask_next_question(user, say)

        elif intent == "end":
            # Only end if the user explicitly said a stop word.
            # Prevents LLM from ending the session for off-topic messages.
            _stop_words = {"end", "stop", "quit", "done", "exit", "bye", "finish"}
            if any(w in message_stripped.split() for w in _stop_words):
                self._end_session(user, say)
            else:
                say(result.get("response", "Still here! Give the question a try, or say `end` to stop."))

        elif intent == "followup":
            # User asked for help — respond naturally, let them answer when ready
            say(result['response'])

        elif intent == "aside":
            # User asked a curiosity question.
            # Try web search + notes for a richer answer; fall back to LLM response.
            aside_tutor_name = (session.get("learner_brief", {}).get("style", {}) or {}).get("tutor_name") or "Sofico"
            enriched = self.response_service.answer_aside_with_search(message, notes_context, tutor_name=aside_tutor_name)
            say(enriched if enriched else result['response'])
            self.repeat_current_question(user, say)

        elif intent == "answer":
            # Graded answer
            score = result["score"]
            if score is None:
                score = 3  # Default if parsing failed

            # Update SM-2 scheduling
            new_schedule = self.sm2.update_schedule(q, score)

            # Store result
            session["results"].append({
                "question_id": q["id"],
                "score": score,
                "feedback": result["response"],
                "new_schedule": new_schedule
            })

            # Show feedback with subtle score
            say(f"{result['response']}\n\n_Score: {score}/5_\n\n---")

            # Move to next question
            session["current_index"] += 1
            self._ask_next_question(user, say)

        else:
            # Unknown intent - treat as answer attempt
            logger.warning(f"Unknown intent: {intent}, treating as answer")
            fallback = "I didn't quite understand that. Try answering the question or say skip/end."
            say(result.get("response", fallback))

    def _handle_self_grade(self, user: str, score: int, say):
        """Handle user's self-assessment when AI grading failed"""
        session = self.active_sessions.get(user)
        if not session:
            return

        q = session.get("pending_question")
        if not q:
            return

        # Clear the pending state
        session["awaiting_self_grade"] = False
        session.pop("pending_question", None)
        session.pop("pending_answer", None)

        # Update SM-2 with self-assessed score
        new_schedule = self.sm2.update_schedule(q, score)

        # Store result
        session["results"].append({
            "question_id": q["id"],
            "score": score,
            "feedback": "Self-assessed",
            "new_schedule": new_schedule,
            "self_graded": True
        })

        say(f"Self-rated: {score}/5. Moving on...\n---")

        # Move to next question
        session["current_index"] += 1
        self._ask_next_question(user, say)

    def _end_session(self, user: str, say):
        """End the session and save results"""
        session = self.active_sessions.get(user)
        if not session:
            return

        # Clear any pending self-grade state
        session.pop("awaiting_self_grade", None)
        session.pop("pending_question", None)
        session.pop("pending_answer", None)

        results = session["results"]
        total_questions = len(session["questions"])
        total_answered = len(results)
        skipped = len([r for r in results if r.get("skipped")])
        graded = [r for r in results if not r.get("skipped") and r.get("score") is not None]
        self_graded = [r for r in graded if r.get("self_graded")]

        if graded:
            avg_score = sum(r["score"] for r in graded) / len(graded)
        else:
            avg_score = 0

        # Save results
        try:
            self.gitlab.save_session_results(user, session)

            # Get LLM-generated closing message
            topics_in_session = ', '.join(set(q['topic'] for q in session["questions"]))
            close_archetype = session.get("archetype", "sophia")
            communication_style = session.get("communication_style", {})
            preference_overrides = session.get("preference_overrides") or {}
            if preference_overrides:
                communication_style = {
                    **communication_style,
                    **preference_overrides.get("communication", {}),
                    **preference_overrides.get("interaction_preferences", {}),
                }
            close_persona = None
            learner_brief = session.get("learner_brief", {}) or {}
            close_tutor_name = (learner_brief.get("style", {}) or {}).get("tutor_name") or "Sofico"
            if learner_brief:
                close_persona = ((learner_brief.get("style", {}) or {}).get("persona_description"))
            if close_persona is None:
                try:
                    close_profile = self.response_service.profile_service.load_profile(user)
                    close_persona = close_profile.get("character", {}).get("persona_description")
                except Exception:
                    close_persona = None
            end_msg = self.response_service.generate_session_closing(
                avg_score,
                topics_in_session,
                close_archetype,
                persona_description=close_persona,
                communication_style=communication_style,
                tutor_name=close_tutor_name,
            )

            # Performance indicator
            if avg_score >= 4:
                perf = "Excellent!"
            elif avg_score >= 3:
                perf = "Good progress!"
            else:
                perf = "Keep practicing!"

            # Build stats message
            stats = f"*Session Complete!* {perf}\n\n"
            stats += f"Questions in session: {total_questions}\n"
            stats += f"Questions answered: {total_answered}\n"

            if skipped > 0:
                stats += f"Skipped: {skipped}\n"
            if self_graded:
                stats += f"Self-graded: {len(self_graded)}\n"

            if graded:
                stats += f"\n*Average score: {avg_score:.1f}/5*\n"

                # Score breakdown
                score_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                for r in graded:
                    score_counts[r["score"]] = score_counts.get(r["score"], 0) + 1

                breakdown = []
                if score_counts[5] > 0:
                    breakdown.append(f"Perfect: {score_counts[5]}")
                if score_counts[4] > 0:
                    breakdown.append(f"Good: {score_counts[4]}")
                if score_counts[3] > 0:
                    breakdown.append(f"OK: {score_counts[3]}")
                if score_counts[2] + score_counts[1] + score_counts[0] > 0:
                    needs_work = score_counts[2] + score_counts[1] + score_counts[0]
                    breakdown.append(f"Needs review: {needs_work}")

                if breakdown:
                    stats += "  " + " | ".join(breakdown) + "\n"

            stats += f"\n{end_msg}"
            say(stats)

            # Generate personalized study guide for weak answers
            weak = [
                r for r in results
                if not r.get("skipped") and r.get("score") is not None and r["score"] < 4
            ]
            if weak:
                self._generate_study_guide(user, session, weak, say)

        except Exception as e:
            logger.error(f"Error saving session: {e}", exc_info=True)
            say("Session ended but I had trouble saving your results. Your progress may not be recorded.")

        # Record completed topic for curriculum hook, then clean up
        topics_in_session = list(set(q["topic"] for q in session.get("questions", [])))
        if len(topics_in_session) == 1:
            self.last_completed_topic[user] = topics_in_session[0]
        self.last_completed_sessions[user] = copy.deepcopy(session)
        del self.active_sessions[user]

    def _generate_study_guide(self, user: str, session: dict, weak_answers: list, say):
        """Generate a personalized mini study guide for concepts that need work."""
        try:
            questions_by_id = {q["id"]: q for q in session.get("questions", [])}

            qa_context = []
            for r in weak_answers:
                q = questions_by_id.get(r["question_id"], {})
                if q.get("text"):
                    qa_context.append({
                        "question": q.get("text", ""),
                        "answer": q.get("answer", ""),
                        "score": r["score"],
                        "topic": q.get("topic", ""),
                    })

            if not qa_context:
                return

            learner_brief = session.get("learner_brief", {}) or {}
            style_brief = learner_brief.get("style", {}) or {}
            profile = self.response_service.profile_service.load_profile(user)
            tutor_name = style_brief.get("tutor_name") or "Sofico"
            persona_description = style_brief.get("persona_description")
            archetype = style_brief.get("archetype") or profile.get("character", {}).get("archetype", "sophia")
            motivation = style_brief.get("motivation") or profile.get("motivations", {}).get("primary", "curiosity")
            name = learner_brief.get("learner_name") or profile.get("metadata", {}).get("learner_name", "Learner")

            archetype_voices = {
                "sophia": "a wise, philosophical mentor who guides through reflection",
                "sensei": "a direct, precise martial arts master who values mastery",
                "grandmother": "a patient, warm teacher who reassures and encourages",
                "research-mentor": "a rigorous research advisor who values evidence and depth",
            }
            motivation_styles = {
                "curiosity": "Highlight surprising connections and what's fascinating about each concept.",
                "achievement": "Frame each explanation as a step toward mastery. Show the progress.",
                "play": "Keep it engaging and light — make the concepts feel like puzzles to crack.",
                "social": "Connect concepts to how they can be explained to or used with others.",
            }

            qa_text = "\n\n".join([
                f"Topic: {qa['topic']}\nQ: {qa['question']}\nCorrect answer: {qa['answer']}\nScore: {qa['score']}/5"
                for qa in qa_context
            ])
            topics = ", ".join(set(qa["topic"] for qa in qa_context))

            voice_block = persona_description or archetype_voices.get(archetype, archetype_voices["sophia"])
            prompt = (
                f"You are {tutor_name}. {voice_block}\n"
                f"You just finished a study session with {name}.\n\n"
                f"These are the concepts {name} found difficult:\n\n{qa_text}\n\n"
                f"Write a short study guide (200-300 words) that:\n"
                f"- Re-explains each concept clearly in your voice\n"
                f"- {motivation_styles.get(motivation, motivation_styles['curiosity'])}\n"
                f"- Uses fresh language — not a repeat of session feedback\n"
                f"- Ends with 2-3 key takeaways\n\n"
                f"Format as clean markdown. Topics: {topics}"
            )

            response = self.response_service.client.messages.create(
                model=self.response_service.model,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}]
            )
            guide = llm_text(response)

            # Save to study-guides folder
            today = date.today().isoformat()
            try:
                self.gitlab.save_study_guide(user, today, guide)
            except Exception as e:
                logger.warning(f"Could not save study guide: {e}")

            say(f"*Study guide for today's session:*\n\n{guide}")

        except Exception as e:
            logger.error(f"Error generating study guide: {e}")

    def _weighted_random_select(self, questions: List[Dict], count: int) -> List[Dict]:
        """
        Select questions with weighted randomization.
        Lower mastery = higher probability of being selected.
        But ALL questions have a chance to appear.
        """
        if len(questions) <= count:
            random.shuffle(questions)
            return questions

        # Calculate weights: lower mastery = higher weight
        # mastery is 0.0 to 1.0, we want weight to be higher for lower mastery
        weights = []
        for q in questions:
            mastery = q.get("mastery", 0.0)
            # Weight formula: (1 - mastery) + 0.1
            # This gives: mastery=0 -> weight=1.1, mastery=1 -> weight=0.1
            # Even mastered questions have some chance (0.1)
            weight = (1.0 - mastery) + 0.1
            weights.append(weight)

        # Use random.choices with weights (allows duplicates, so we need to handle that)
        selected = []
        remaining = list(range(len(questions)))
        remaining_weights = weights.copy()

        for _ in range(count):
            if not remaining:
                break

            # Select one index based on weights
            chosen_idx = random.choices(remaining, weights=remaining_weights, k=1)[0]

            # Find position in remaining list and remove it
            pos = remaining.index(chosen_idx)
            remaining.pop(pos)
            remaining_weights.pop(pos)

            selected.append(questions[chosen_idx])

        return selected

    def _interleave_questions(self, questions: List[Dict]) -> List[Dict]:
        """
        Shuffle questions so no two consecutive questions share the same topic.
        Feels random, not folder-by-folder.
        """
        questions = list(questions)
        random.shuffle(questions)

        result = []
        deferred = []

        for q in questions:
            if result and result[-1].get("topic") == q.get("topic"):
                deferred.append(q)
            else:
                result.append(q)
                # Try to slot in any deferred questions now that topic has changed
                still_deferred = []
                for dq in deferred:
                    if result[-1].get("topic") != dq.get("topic"):
                        result.append(dq)
                    else:
                        still_deferred.append(dq)
                deferred = still_deferred

        result.extend(deferred)
        return result

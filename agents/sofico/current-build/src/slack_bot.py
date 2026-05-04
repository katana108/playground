"""
Sofi Slack Bot
Handles Slack connections and routes messages to handlers
"""

import os
import logging
import time
from datetime import datetime, timedelta
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from handlers.study_handler import StudyHandler
from handlers.upload_handler import UploadHandler
from handlers.progress_handler import ProgressHandler
from handlers.onboarding_handler import OnboardingHandler
from handlers.explanation_handler import ExplanationHandler
from handlers.curriculum_handler import CurriculumHandler
from services.sm2_service import SM2Service
from services.session_response_service import SessionResponseService
from services.profile_service import ProfileService
from services.conversation_memory_service import ConversationMemoryService
from orchestrator import ConversationState, SofiOrchestrator, SoficoOnboardingFlow, TurnContext
from orchestrator.session_controller import SessionController

logger = logging.getLogger(__name__)

RECENT_TASK_MAX_AGE_MINUTES = 30


class SofiSlackBot:
    """Main Slack bot for Sofi"""

    def __init__(self):
        # Initialize Slack app
        self.app = App(token=os.getenv("SLACK_BOT_TOKEN"))

        # Initialize services - use local files for testing, GitLab for production
        if os.getenv("SOFI_USE_LOCAL_FILES", "true").lower() == "true":
            from services.local_file_service import LocalFileService
            self.data_service = LocalFileService()
            logger.info("Using LocalFileService for data")
        else:
            from services.gitlab_service import GitLabService
            self.data_service = GitLabService()
            logger.info("Using GitLabService for data")

        self.sm2_service = SM2Service()
        self.profile_service = ProfileService(data_service=self.data_service)
        self.memory_service = ConversationMemoryService(data_service=self.data_service)
        self.session_response_service = SessionResponseService(
            data_service=self.data_service,
            memory_service=self.memory_service
        )
        self.sofico_orchestrator = SofiOrchestrator(
            profile_service=self.profile_service,
            memory_service=self.memory_service,
            data_service=self.data_service,
            session_response_service=self.session_response_service,
        )
        self.sofico_onboarding = SoficoOnboardingFlow(
            student_model_store=self.sofico_orchestrator.bootstrap_loader.student_model_store,
            profile_service=self.profile_service,
        )

        # Initialize handlers
        self.study_handler = StudyHandler(
            gitlab_service=self.data_service,
            sm2_service=self.sm2_service,
            session_response_service=self.session_response_service
        )
        self.upload_handler = UploadHandler(
            gitlab_service=self.data_service,
            slack_app=self.app,
            session_response_service=self.session_response_service
        )
        self.progress_handler = ProgressHandler(
            gitlab_service=self.data_service
        )
        self.onboarding_handler = OnboardingHandler(
            data_service=self.data_service,
            profile_service=self.profile_service,
            session_response_service=self.session_response_service
        )
        self.explanation_handler = ExplanationHandler(
            data_service=self.data_service,
            session_response_service=self.session_response_service,
            profile_service=self.profile_service
        )
        self.curriculum_handler = CurriculumHandler(
            data_service=self.data_service,
            session_response_service=self.session_response_service,
            profile_service=self.profile_service
        )

        # Deduplication: track recently processed (user_id, ts) pairs
        self._recent_events: dict = {}
        self._pending_preference_updates: dict = {}
        self._temporary_preference_overrides: dict = {}
        self._sofico_sessions: dict = {}

        # Register event handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register Slack event handlers"""

        # Handle direct messages and mentions
        @self.app.event("app_mention")
        def handle_mention(event, say):
            # Skip DMs — they're handled by the message event below.
            # Without this, a message in a DM fires BOTH events → duplicate responses.
            if event.get("channel_type") == "im":
                return
            self._route_message(event, say)

        @self.app.event("message")
        def handle_message(event, say):
            # Only respond to DMs (not channel messages without mention)
            # Skip subtypes: bot_message, message_changed, message_deleted, etc.
            if event.get("channel_type") == "im" and event.get("subtype") is None:
                self._route_message(event, say)

        # Handle file uploads — DMs only, deduplicate by file_id
        @self.app.event("file_shared")
        def handle_file(event, say):
            # Only process files shared in DMs (channel IDs starting with "D")
            channel_id = event.get("channel_id", "")
            if not channel_id.startswith("D"):
                return
            # Deduplicate: Slack retries if processing takes >3s; file_id is stable
            file_id = event.get("file_id", "")
            user_id = event.get("user_id") or event.get("user", "")
            if file_id and self._is_duplicate(user_id, f"file:{file_id}"):
                logger.info(f"Skipping duplicate file_shared for file_id={file_id}")
                return
            student_model = self.sofico_orchestrator.bootstrap_loader.load_student_model(user_id)
            needs_onboarding = self.sofico_onboarding.needs_onboarding(student_model)
            if not needs_onboarding:
                self.sofico_onboarding.clear(user_id)
            if self.sofico_onboarding.is_active(user_id) or needs_onboarding:
                if self.sofico_onboarding.is_active(user_id):
                    say("Finish the quick Sofico setup first, then upload the file.")
                else:
                    say(self.sofico_onboarding.start(user_id))
                return
            ingest_result = self.upload_handler.handle_file_upload(event, say)
            followup_outputs = self._get_sofico_session(user_id).register_external_ingest_result(
                ingest_result,
                source_message=f"slack file upload {file_id}",
            )
            for output in followup_outputs:
                slack_text = self._format_sofico_output_for_slack(output)
                if slack_text:
                    say(slack_text)

    def _route_message(self, event, say):
        """Route message to appropriate handler based on content"""
        user = event.get("user")
        # Skip bot messages and system messages that have no user
        if not user:
            return

        try:
            self._handle_message(event, say, user)
        except Exception as e:
            logger.error(f"Unhandled error routing message for {user}: {e}", exc_info=True)
            try:
                say("Something went wrong on my end — please try again in a moment.")
            except Exception:
                pass

    def _is_duplicate(self, user: str, ts: str) -> bool:
        """Return True if this (user, ts) was already processed recently.

        setdefault is atomic in CPython — it inserts only if the key is absent
        and returns the stored value in one step, eliminating the check-then-set
        race where two threads both pass the 'key in dict' test simultaneously.
        """
        key = f"{user}:{ts}"
        now = time.time()
        stored = self._recent_events.setdefault(key, now)
        if stored != now:
            return True
        # Prune entries older than 60 seconds to avoid unbounded growth
        if len(self._recent_events) > 200:
            cutoff = now - 60
            self._recent_events = {k: v for k, v in self._recent_events.items() if v > cutoff}
        return False

    def _handle_message(self, event, say, user):
        """Internal handler — called by _route_message inside a try/except."""
        ts = event.get("ts", "")
        if ts and self._is_duplicate(user, ts):
            logger.info(f"Skipping duplicate event for {user} ts={ts}")
            return

        raw_text = event.get("text", "")

        # Remove bot mention if present, but preserve the learner's original casing.
        raw_text = self._clean_message(raw_text)
        raw_text_stripped = raw_text.strip()
        normalized_text = raw_text_stripped.lower()

        logger.info(f"Received message from {user}: {raw_text_stripped}")

        if self._handle_with_sofico_session(user, raw_text_stripped, say):
            return

        # Wrap say() to capture Sofi's responses into the buffer
        memory_say = self._make_memory_say(user, say)

        stored_messages = self.memory_service.get_history(user)
        orchestrator_turn = TurnContext(
            user_id=user,
            message=raw_text_stripped,
            normalized_message=normalized_text,
            channel_id=event.get("channel", ""),
            message_ts=ts,
            source="slack",
        )
        orchestrator_state = ConversationState(metadata={"stored_messages": stored_messages})
        orchestrator_result = self.sofico_orchestrator.handle_turn(orchestrator_turn, orchestrator_state)
        selected_capability = (orchestrator_result.params or {}).get("capability")

        student_model = self.sofico_orchestrator.bootstrap_loader.load_student_model(user)
        needs_onboarding = self.sofico_onboarding.needs_onboarding(student_model)
        if not needs_onboarding:
            self.sofico_onboarding.clear(user)

        if self.sofico_onboarding.is_active(user):
            self.memory_service.add_message(user, "user", raw_text_stripped)
            onboarding_result = self.sofico_onboarding.handle(user, raw_text_stripped)
            memory_say(onboarding_result["reply"])
            return

        if selected_capability == "onboard_user" and needs_onboarding:
            self.memory_service.add_message(user, "user", raw_text_stripped)
            memory_say(self.sofico_onboarding.start(user))
            return

        # ── FIRST: Active onboarding takes priority ───────────────────────────
        # Check onboarding BEFORE timeout — timeout generates a 6-second API call
        # which causes a noticeable delay and makes users re-send messages.
        onboarding_active = self.onboarding_handler.is_active(user)
        onboarding_notice = self.onboarding_handler.take_state_notice(user)
        if onboarding_active:
            mode_request = self._classify_active_mode_shift(user, raw_text_stripped, normalized_text, "onboarding")
            if mode_request and mode_request["kind"] == "explicit":
                self.onboarding_handler.persist_partial_profile(user)
                self._dispatch_direct_action(mode_request["action"], mode_request.get("params", {}), event, user, memory_say)
                return
            if mode_request and mode_request["kind"] == "ambiguous":
                self.memory_service.add_message(user, "user", raw_text_stripped)
                memory_say("Do you want to keep shaping your setup, or switch to something like a lesson, quiz, or study plan?")
                return

            if self._should_bypass_update_onboarding(user, normalized_text):
                self.onboarding_handler.persist_partial_profile(user)
            else:
                self.memory_service.add_message(user, "user", raw_text_stripped)
                if normalized_text in ["skip setup", "skip", "skip onboarding"]:
                    self.onboarding_handler.clear(user)
                    memory_say("No problem! Say *quiz me* whenever you're ready.")
                    return
                self.onboarding_handler.handle(event, memory_say)
                return

        # ── Memory: check timeout, add to buffer ─────────────────────────────
        timed_out = self.memory_service.check_timeout(user)
        if timed_out:
            self._temporary_preference_overrides.pop(user, None)
            self._clear_recent_task_state(user)
        self.memory_service.add_message(user, "user", raw_text_stripped)

        if onboarding_notice and self._should_surface_state_notice(normalized_text, "onboarding"):
            memory_say(onboarding_notice)

        # ── AUTO-ONBOARD: Brand new user, but don't block explicit task requests ─────────
        if self._should_auto_onboard(user, normalized_text):
            self.onboarding_handler.start(user, memory_say)
            return

        # ── PENDING UPLOAD: Topic confirmation waiting ────────────────────────
        if self.upload_handler.has_pending(user):
            self.upload_handler.handle_pending(user, raw_text_stripped, memory_say)
            return

        # ── ACTIVE CURRICULUM SESSION ─────────────────────────────────────────
        curriculum_active = self.curriculum_handler.is_active(user)
        curriculum_notice = self.curriculum_handler.take_state_notice(user)
        if curriculum_active:
            mode_request = self._classify_active_mode_shift(user, raw_text_stripped, normalized_text, "curriculum")
            if mode_request and mode_request["kind"] == "explicit":
                self._dispatch_direct_action(mode_request["action"], mode_request.get("params", {}), event, user, memory_say)
                return
            if mode_request and mode_request["kind"] == "ambiguous":
                memory_say("Do you want to keep going with this lesson, switch tasks, or pause here?")
                return

            post_action = self.curriculum_handler.handle(user, raw_text_stripped, memory_say)
            if post_action:
                self._handle_post_action(post_action, event, user, memory_say)
            return
        if curriculum_notice and self._should_surface_state_notice(normalized_text, "curriculum"):
            memory_say(curriculum_notice)

        # ── ACTIVE EXPLANATION SESSION ────────────────────────────────────────
        if self.explanation_handler.is_active(user):
            mode_request = self._classify_active_mode_shift(user, raw_text_stripped, normalized_text, "explanation")
            if mode_request and mode_request["kind"] == "explicit":
                self.explanation_handler.cancel(user)
                self._dispatch_direct_action(mode_request["action"], mode_request.get("params", {}), event, user, memory_say)
                return
            if mode_request and mode_request["kind"] == "ambiguous":
                memory_say("Do you want me to keep explaining, wrap up, or switch to something else?")
                return

            post_action = self.explanation_handler.handle(
                user,
                raw_text_stripped,
                memory_say,
                preference_overrides=self._temporary_preference_overrides.get(user),
            )
            if post_action:
                self._handle_post_action(post_action, event, user, memory_say)
            return

        # ── ACTIVE STUDY SESSION ──────────────────────────────────────────────
        if user in self.study_handler.active_sessions:
            mode_request = self._classify_active_mode_shift(user, raw_text_stripped, normalized_text, "study")
            if mode_request and mode_request["kind"] == "explicit":
                self.study_handler.cancel_session(user)
                self._dispatch_direct_action(mode_request["action"], mode_request.get("params", {}), event, user, memory_say)
                return
            if mode_request and mode_request["kind"] == "ambiguous":
                memory_say("Do you want to answer this question, skip it, end the quiz, or switch to something else?")
                return

            self.study_handler.handle(
                event,
                memory_say,
                preference_overrides=self._temporary_preference_overrides.get(user),
            )
            if user not in self.study_handler.active_sessions:
                self.memory_service.end_session(user)
                # Notify curriculum handler in case this was a curriculum lesson
                self._notify_curriculum_lesson_complete(user, memory_say)
            return

        # ── PENDING PREFERENCE UPDATE ────────────────────────────────────────
        # Only runs when no active session — won't interrupt a quiz or explanation.
        if self._has_pending_preference_update(user):
            self._handle_pending_preference_update(user, normalized_text, memory_say)
            return

        # ── LIVE PREFERENCE FEEDBACK ─────────────────────────────────────────
        preference_signal = self._detect_preference_feedback(normalized_text)
        if preference_signal:
            self._start_preference_update(user, preference_signal, memory_say)
            return

        # ── RECENT TASK CONTINUATION ─────────────────────────────────────────
        recent_task = self._load_recent_task_state(user)
        if self._should_resume_recent_task(normalized_text, recent_task):
            if self._resume_recent_task(user, recent_task, event, memory_say):
                return

        # ── FOURTH: Sofi is the brain ─────────────────────────────────────────
        history = self.memory_service.get_history(user)
        available_topics = self.data_service.get_available_topics(user)
        memory_context = self.memory_service.get_memory_context(user)

        result = self.session_response_service.get_sofi_response(
            message=raw_text_stripped,
            user_id=user,
            history=history,
            available_topics=available_topics,
            memory_context=memory_context,
            preference_overrides=self._temporary_preference_overrides.get(user),
        )

        sofi_message = result.get("message", "")
        action = result.get("action")
        params = result.get("params", {})

        logger.info(f"Sofi action: {action}")

        self._execute_action(action, params, event, user, memory_say, sofi_message=sofi_message)

        # Passively capture name from conversation if profile has none yet
        self._capture_name_if_missing(user)

    def _execute_action(self, action, params, event, user, say, sofi_message: str = ""):
        """Execute a routed action, optionally reusing Sofi's opening message."""
        handler_opens = {"quiz", "explain", "customize", "curriculum", "progress", "upload"}
        if sofi_message and action not in handler_opens:
            say(sofi_message)

        if action == "quiz":
            topic = params.get("topic")
            self._save_recent_task_state(
                user,
                {
                    "kind": "quiz",
                    "topic": topic or "",
                    "updated_at": datetime.now().isoformat(),
                }
            )
            if topic:
                event_copy = dict(event)
                event_copy["text"] = f"quiz me on {topic}"
                self.study_handler.handle(
                    event_copy,
                    say,
                    preference_overrides=self._temporary_preference_overrides.get(user),
                )
            else:
                self.study_handler.handle(
                    event,
                    say,
                    preference_overrides=self._temporary_preference_overrides.get(user),
                )
            if user not in self.study_handler.active_sessions:
                self.memory_service.end_session(user)
            return

        if action == "explain":
            topic = params.get("topic")
            self._save_recent_task_state(
                user,
                {
                    "kind": "explain",
                    "topic": topic or "",
                    "updated_at": datetime.now().isoformat(),
                }
            )
            if topic:
                self.explanation_handler.start(
                    user,
                    topic,
                    say,
                    preference_overrides=self._temporary_preference_overrides.get(user),
                    from_curriculum=self.curriculum_handler.is_active(user),
                )
            else:
                say(sofi_message or "Which topic would you like me to walk you through?")
            return

        if action == "progress":
            if self.memory_service.is_weekly_report_due(user):
                report = self.memory_service.generate_and_save_weekly_report(user)
                if report:
                    say(report)
            self.progress_handler.handle(event, say)
            return

        if action == "upload":
            self.upload_handler.handle(event, say)
            return

        if action == "customize":
            self._save_recent_task_state(
                user,
                {
                    "kind": "customize",
                    "updated_at": datetime.now().isoformat(),
                }
            )
            self.onboarding_handler.start(user, say, is_update=True, opening=sofi_message or None)
            return

        if action == "curriculum":
            subject = (params.get("subject") or "").strip()
            if not subject:
                say(sofi_message or "What subject do you want to build a study plan for?")
                return
            self._save_recent_task_state(
                user,
                {
                    "kind": "curriculum",
                    "subject": subject,
                    "updated_at": datetime.now().isoformat(),
                }
            )
            self.curriculum_handler.start(user, subject, say, opening=sofi_message or None)

    def _dispatch_direct_action(self, action, params, event, user, say):
        """Execute an explicit mode switch without asking the general chat brain first."""
        self._execute_action(action, params, event, user, say, sofi_message="")

    def _capture_name_if_missing(self, user_id: str):
        """Save a minimal profile if no name is known yet — lets the brain address the user."""
        try:
            profile = self.profile_service.load_profile(user_id)
            if profile.get("metadata", {}).get("learner_name"):
                return  # already have a name
            history = self.memory_service.get_history(user_id)
            # Convert memory history format to the format _extract_name_from_history expects
            msgs = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in history]
            name = self.onboarding_handler._extract_name_from_history(msgs)
            if not name:
                return
            from datetime import date
            minimal_profile = {
                "metadata": {
                    "learner_name": name,
                    "created": date.today().isoformat(),
                    "last_updated": date.today().isoformat(),
                },
                "character": {"archetype": "sophia", "persona_description": None},
                "learning_level": {"general": "intermediate"},
                "motivations": {"primary": "curiosity"},
                "sensitivity": {"error_sensitivity": "medium"},
                "feedback_preferences": {
                    "style": "analytical-encouraging", "criticism_directness": "medium",
                    "tone": "formal-warm", "detail_level": "medium", "use_emojis": False,
                },
                "interests": {"background_knowledge": []},
                "explanation_preferences": {"chunk_size": "medium", "style": "narrative"},
                "communication": {
                    "verbosity": "concise", "theatricality": "subtle", "humor_style": "light",
                    "metaphor_preferences": {"preferred": ["human-experience"], "avoid": []},
                    "explanation_depth": "moderate",
                },
                "interaction_preferences": {
                    "proactivity": "medium", "customization_mode": "quick",
                    "preference_update_style": "confirm-before-saving",
                },
                "session_preferences": {"preferred_session_size": 15, "interleaving_enabled": True},
            }
            self.data_service.save_profile(user_id, minimal_profile)
            self.profile_service.invalidate_cache(user_id)
            logger.info(f"Saved minimal profile for {user_id} with name={name}")
        except Exception as e:
            logger.warning(f"Could not save minimal profile for {user_id}: {e}")

    def _classify_active_mode_shift(self, user_id: str, raw_text: str, normalized_text: str, mode: str):
        """Decide whether an active-mode message is an explicit switch, an ambiguous nudge, or normal in-mode input."""
        ambiguous_words = {
            "continue", "go on", "keep going", "carry on", "ok", "okay",
            "next", "start", "wait", "hold on", "let's go", "lets go",
        }
        if normalized_text in ambiguous_words:
            if mode in {"onboarding", "explanation", "study"}:
                return {"kind": "ambiguous"}
            return None

        explicit = self.session_response_service._infer_explicit_action(
            raw_text,
            self.data_service.get_available_topics(user_id),
        )
        if not explicit:
            return None

        action = explicit.get("action")
        if not action:
            return None

        if mode == "onboarding":
            if action != "customize":
                return {"kind": "explicit", "action": action, "params": explicit.get("params", {})}
            return None

        if mode == "curriculum":
            if action in {"customize", "progress", "upload", "curriculum"}:
                return {"kind": "explicit", "action": action, "params": explicit.get("params", {})}
            return None

        if mode == "explanation":
            if action in {"quiz", "customize", "progress", "upload", "curriculum"}:
                return {"kind": "explicit", "action": action, "params": explicit.get("params", {})}
            return None

        if mode == "study":
            if action in {"explain", "customize", "progress", "upload", "curriculum"}:
                return {"kind": "explicit", "action": action, "params": explicit.get("params", {})}
            return None

        return None

    def _should_surface_state_notice(self, normalized_text: str, mode: str) -> bool:
        """Only surface stale-state notices when the learner seems to still be engaging with that mode."""
        if normalized_text in {"continue", "go on", "keep going", "carry on", "next", "start", "let's go", "lets go"}:
            return True

        if mode == "onboarding":
            relevant_words = ("setup", "preferences", "customize", "style", "teach")
        else:
            relevant_words = ("curriculum", "plan", "lesson", "course", "study plan", "continue")
        return any(word in normalized_text for word in relevant_words)

    def _save_recent_task_state(self, user_id: str, state: dict):
        """Persist a small explicit record of the most recent high-level task."""
        self.memory_service.add_system_note(
            user_id,
            " ".join(f"{key}={value}" for key, value in state.items() if value)
        )
        if hasattr(self.data_service, "save_recent_task_state"):
            try:
                self.data_service.save_recent_task_state(user_id, state)
            except Exception as e:
                logger.warning(f"Could not persist recent task state for {user_id}: {e}")

    def _load_recent_task_state(self, user_id: str) -> dict:
        """Load recent task state if present and still fresh enough to matter."""
        if not hasattr(self.data_service, "load_recent_task_state"):
            return {}
        try:
            state = self.data_service.load_recent_task_state(user_id) or {}
        except Exception as e:
            logger.warning(f"Could not load recent task state for {user_id}: {e}")
            return {}

        updated_at = state.get("updated_at")
        if not updated_at:
            return state
        try:
            ts = datetime.fromisoformat(updated_at)
            if datetime.now() - ts > timedelta(minutes=RECENT_TASK_MAX_AGE_MINUTES):
                self._clear_recent_task_state(user_id)
                return {}
        except ValueError:
            logger.warning(f"Invalid recent task timestamp for {user_id}: {updated_at}")
            self._clear_recent_task_state(user_id)
            return {}
        return state

    def _clear_recent_task_state(self, user_id: str):
        """Clear recent task state from persistence if supported."""
        if hasattr(self.data_service, "clear_recent_task_state"):
            try:
                self.data_service.clear_recent_task_state(user_id)
            except Exception as e:
                logger.warning(f"Could not clear recent task state for {user_id}: {e}")

    def _should_resume_recent_task(self, text: str, recent_task: dict) -> bool:
        """Detect vague follow-ups that should resume a recent high-level task."""
        if not recent_task:
            return False
        return text.lower().strip() in {"continue", "go on", "keep going", "carry on"}

    def _resume_recent_task(self, user_id: str, recent_task: dict, event: dict, say) -> bool:
        """Resume a recent high-level task deterministically."""
        kind = recent_task.get("kind")
        if kind == "curriculum":
            subject = recent_task.get("subject", "").strip()
            if subject and not self.curriculum_handler.is_active(user_id):
                self.curriculum_handler.start(user_id, subject, say)
                return True
        if kind == "explain":
            topic = recent_task.get("topic", "").strip()
            if topic and not self.explanation_handler.is_active(user_id):
                self.explanation_handler.start(
                    user_id,
                    topic,
                    say,
                    preference_overrides=self._temporary_preference_overrides.get(user_id),
                )
                return True
        if kind == "quiz":
            topic = recent_task.get("topic", "").strip()
            event_copy = dict(event)
            if topic:
                event_copy["text"] = f"quiz me on {topic}"
            self.study_handler.handle(
                event_copy,
                say,
                preference_overrides=self._temporary_preference_overrides.get(user_id),
            )
            return True
        return False

    def _should_auto_onboard(self, user_id: str, text: str) -> bool:
        """Only auto-start onboarding for new users when they are not already asking for a concrete task."""
        if not self._is_new_user(user_id):
            return False

        normalized = text.lower().strip()
        task_phrases = (
            "quiz", "explain", "study", "lesson", "curriculum", "plan", "teach",
            "process this", "upload", "review", "course", "flashcards", "anki",
        )
        greeting_phrases = {
            "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
            "start", "help", "yo",
        }

        if any(phrase in normalized for phrase in task_phrases):
            return False
        return normalized in greeting_phrases or len(normalized.split()) <= 3

    def _should_bypass_update_onboarding(self, user_id: str, text: str) -> bool:
        """Let task requests escape a stale profile-update flow instead of being trapped inside it."""
        session = self.onboarding_handler.active_onboardings.get(user_id, {})
        if not session.get("is_update"):
            return False

        profile = self.profile_service.load_profile(user_id)
        if not profile.get("metadata", {}).get("learner_name"):
            return False

        normalized = text.lower().strip()
        task_phrases = (
            "first lesson", "start lesson", "start creating lessons", "create lessons",
            "course info", "study plan", "curriculum", "teach me", "teach this",
            "give me the lesson", "continue lesson", "continue", "quiz me", "explain it",
            "walk me through", "start learning", "let's learn",
        )
        customization_phrases = (
            "customize", "change your style", "change how you teach", "update preferences",
            "less wordy", "more concise", "more chatty", "less intense", "more playful",
            "be gentler", "be more direct", "feedback style", "teaching style",
        )

        if any(phrase in normalized for phrase in customization_phrases):
            return False
        return any(phrase in normalized for phrase in task_phrases)

    def _notify_curriculum_lesson_complete(self, user_id: str, say):
        """Tell the curriculum handler when a study session ends, in case it was a lesson."""
        try:
            completed_topic = getattr(self.study_handler, "last_completed_topic", {}).get(user_id)
            if completed_topic:
                self.curriculum_handler.on_lesson_complete(user_id, completed_topic, say)
        except Exception as e:
            logger.warning(f"Curriculum lesson complete notification failed: {e}")

    def _has_pending_preference_update(self, user_id: str) -> bool:
        return user_id in self._pending_preference_updates

    def _detect_preference_feedback(self, text: str):
        """Detect simple live-tuning feedback from natural conversation."""
        normalized = text.lower().strip()
        signals = [
            (("too wordy", "talking too much", "too long", "be shorter", "less wordy", "more concise", "be more concise"), "communication.verbosity", "concise", "be more concise"),
            (("be more detailed", "be more chatty", "be chattier", "talk more like this"), "communication.verbosity", "chatty", "be more chatty"),
            (("too intense", "less intense", "dial it down", "more calm", "be calmer"), "communication.theatricality", "subtle", "be less intense"),
            (("more dramatic", "more theatrical", "lean into the persona", "more vivid"), "communication.theatricality", "vivid", "be more theatrical"),
            (("less proactive", "stop suggesting things", "stop pushing", "don't suggest so much"), "interaction_preferences.proactivity", "low", "be less proactive"),
            (("more proactive", "suggest more", "take more initiative"), "interaction_preferences.proactivity", "high", "be more proactive"),
            (("less funny", "less humor", "stop joking", "too jokey"), "communication.humor_style", "none", "use less humor"),
            (("more playful", "be more playful", "be funnier", "more humor"), "communication.humor_style", "playful", "be more playful"),
        ]

        for phrases, path, value, label in signals:
            if any(phrase in normalized for phrase in phrases):
                return {"path": path, "value": value, "label": label}
        return None

    def _start_preference_update(self, user_id: str, update: dict, say):
        """Ask whether a detected preference change should be temporary or permanent."""
        self._pending_preference_updates[user_id] = update
        say(
            f"I can do that and {update['label']}.\n\n"
            f"Do you want that *just for now* or *from now on*?\n"
            f"If you want, you can also just say *yes* and I'll save it as a lasting preference."
        )

    def _handle_pending_preference_update(self, user_id: str, text: str, say):
        """Resolve temporary vs permanent preference updates."""
        update = self._pending_preference_updates.get(user_id)
        if not update:
            return

        normalized = text.lower().strip()
        temporary_words = {"for now", "just for now", "temporarily", "temporary", "this session", "today only"}
        permanent_words = {"from now on", "permanently", "permanent", "save it", "yes", "yeah", "yep", "please do"}
        cancel_words = {"no", "cancel", "never mind", "nevermind", "don't change it", "leave it"}

        if any(word in normalized for word in temporary_words):
            self._apply_temporary_preference_update(user_id, update)
            self._pending_preference_updates.pop(user_id, None)
            say("Okay. I'll treat that as a temporary adjustment for this conversation.")
            return

        if any(word in normalized for word in permanent_words):
            self._save_preference_update(user_id, update)
            self._pending_preference_updates.pop(user_id, None)
            say("Okay. I've saved that as part of how I should teach you going forward.")
            return

        if any(word in normalized for word in cancel_words):
            self._pending_preference_updates.pop(user_id, None)
            say("No problem. I won't change that preference.")
            return

        say("I still need to know whether you want that *just for now* or *from now on*.")

    def _apply_temporary_preference_update(self, user_id: str, update: dict):
        """Store a temporary preference override for this conversation."""
        overrides = self._temporary_preference_overrides.setdefault(user_id, {})
        self._set_nested_value(overrides, update["path"], update["value"])

    def _save_preference_update(self, user_id: str, update: dict):
        """Persist a preference update into the learner profile."""
        profile = self.profile_service.load_profile(user_id)
        if "metadata" not in profile:
            profile["metadata"] = {}
        profile["metadata"]["last_updated"] = time.strftime("%Y-%m-%d")
        self._set_nested_value(profile, update["path"], update["value"])
        self.data_service.save_profile(user_id, profile)
        self.profile_service.invalidate_cache(user_id)

        temp_overrides = self._temporary_preference_overrides.get(user_id)
        if temp_overrides:
            self._remove_nested_value(temp_overrides, update["path"])
            if not temp_overrides:
                self._temporary_preference_overrides.pop(user_id, None)

    def _set_nested_value(self, data: dict, path: str, value):
        """Set a dotted-path value inside a nested dict."""
        parts = path.split(".")
        target = data
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value

    def _remove_nested_value(self, data: dict, path: str):
        """Remove a dotted-path value from a nested dict if present."""
        parts = path.split(".")
        target = data
        parents = []
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                return
            parents.append((target, part))
            target = target[part]
        target.pop(parts[-1], None)
        for parent, key in reversed(parents):
            if isinstance(parent.get(key), dict) and not parent[key]:
                parent.pop(key, None)

    def _handle_post_action(self, post_action, event, user_id: str, say):
        """Handle action hand-offs returned from active handlers."""
        if isinstance(post_action, str):
            post_action = {"action": post_action}

        action = post_action.get("action")
        topic = post_action.get("topic")

        if action == "customize":
            self.onboarding_handler.start(user_id, say, is_update=True)
            return

        if action == "quiz":
            event_copy = dict(event)
            if topic:
                event_copy["text"] = f"quiz me on {topic}"
            self.study_handler.handle(
                event_copy,
                say,
                preference_overrides=self._temporary_preference_overrides.get(user_id),
            )
            return

        if action == "explain":
            if topic:
                self.explanation_handler.start(
                    user_id,
                    topic,
                    say,
                    preference_overrides=self._temporary_preference_overrides.get(user_id),
                    from_curriculum=self.curriculum_handler.is_active(user_id),
                )
            else:
                say("Tell me what you'd like me to walk you through.")
            return

        if action == "end" and topic:
            try:
                self.curriculum_handler.on_lesson_complete(user_id, topic, say)
            except Exception as e:
                logger.warning(f"Curriculum lesson complete notification failed: {e}")

    def _make_memory_say(self, user_id: str, say):
        """Wrap say() to capture Sofi's responses into the conversation buffer."""
        memory_service = self.memory_service

        def memory_say(text, **kwargs):
            result = say(text, **kwargs)
            if isinstance(text, str):
                memory_service.add_message(user_id, "assistant", text)
            return result

        return memory_say

    def _handle_with_sofico_session(self, user_id: str, text: str, say) -> bool:
        """Route the Slack text message through the new Sofico session controller."""
        if self._should_use_legacy_handler(text):
            return False

        controller = self._get_sofico_session(user_id)
        outputs = controller.handle_input(text)
        for output in outputs:
            slack_text = self._format_sofico_output_for_slack(output)
            if slack_text:
                say(slack_text)
        return True

    def _get_sofico_session(self, user_id: str) -> SessionController:
        """Return one reusable Sofico session controller per Slack user."""
        controller = self._sofico_sessions.get(user_id)
        if controller:
            return controller

        controller = SessionController(
            project_root=self.sofico_orchestrator.project_root,
            user_id=user_id,
            data_service=self.data_service,
            memory_service=self.memory_service,
            profile_service=self.profile_service,
            session_response_service=self.session_response_service,
            orchestrator=self.sofico_orchestrator,
            onboarding_flow=self.sofico_onboarding,
            upload_handler=self.upload_handler,
            explanation_handler=self.explanation_handler,
            study_handler=self.study_handler,
            progress_handler=self.progress_handler,
            curriculum_handler=self.curriculum_handler,
            source="slack",
            include_debug=False,
        )
        self._sofico_sessions[user_id] = controller
        return controller

    def _format_sofico_output_for_slack(self, output: str) -> str:
        """Remove local harness labels before sending messages to Slack."""
        if not output:
            return ""
        if output.startswith("[capability]"):
            return ""
        if output.startswith("Sofico: "):
            return output[len("Sofico: "):]
        return output

    def _should_use_legacy_handler(self, text: str) -> bool:
        """The Sofico session controller now owns text-turn execution."""
        return False

    def _clean_message(self, text):
        """Remove bot mention from message"""
        import re
        return re.sub(r'<@[A-Z0-9]+>', '', text).strip()

    def _is_new_user(self, user: str) -> bool:
        """Return True if this user has no profile and no sessions yet."""
        try:
            profile = self.profile_service.load_profile(user)
            has_profile = bool(profile.get("metadata", {}).get("learner_name"))
            if has_profile:
                return False
            stats = self.data_service.get_user_stats(user)
            return stats.get("total_sessions", 0) == 0
        except Exception:
            return False

    def run(self):
        """Start the bot"""
        logger.info("Sofi is starting...")
        handler = SocketModeHandler(self.app, os.getenv("SLACK_APP_TOKEN"))
        handler.start()

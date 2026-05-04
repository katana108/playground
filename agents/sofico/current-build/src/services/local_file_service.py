"""
Local File Service
Reads learner data from local filesystem (for testing without GitLab)
"""

import os
import logging
import copy
import yaml
from pathlib import Path
from datetime import date
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class LocalFileService:
    """Reads learner data from local filesystem"""

    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or os.getenv(
            "SOFI_LEARNERS_PATH",
            str(Path(__file__).resolve().parent.parent.parent / "learners")
        ))
        logger.info(f"LocalFileService initialized with base_path: {self.base_path}")

    def get_due_questions(self, user_id: str, topic_filter: str = None) -> List[Dict[str, Any]]:
        """Get all questions due for review for a user, optionally filtered by topic"""
        questions = []
        today = date.today().isoformat()

        learner_path = self.base_path / self._user_folder(user_id)
        topics_path = learner_path / "topics"

        if not topics_path.exists():
            logger.warning(f"Topics path not found: {topics_path}")
            return []

        # Iterate through topic folders
        for topic_dir in topics_path.iterdir():
            if not topic_dir.is_dir() or topic_dir.name.startswith('.'):
                continue

            # Apply topic filter if specified
            if topic_filter:
                folder = topic_dir.name.lower()
                filter_lower = topic_filter.lower()
                # Full substring match first
                if filter_lower not in folder:
                    # Fall back to word-level match: any significant word in filter
                    # must appear in the folder name (e.g. "portuguese" in "language" → no match,
                    # but "portuguese language" → "portuguese" matches "portuguese-verbs")
                    filter_words = [w for w in filter_lower.split() if len(w) > 3]
                    if not any(w in folder for w in filter_words):
                        continue

            index_path = topic_dir / "_index.yaml"
            if not index_path.exists():
                continue

            try:
                with open(index_path, 'r') as f:
                    index_data = yaml.safe_load(f)

                # Load full question texts and answers from the markdown document
                doc_content = self._load_document_answers(topic_dir)

                for q in index_data.get("questions", []):
                    next_review = q.get("next_review")
                    if next_review is None or next_review <= today:
                        q["topic"] = topic_dir.name
                        doc_q = doc_content.get(q["id"], {})

                        # Use full question text from markdown if index text looks truncated
                        md_question = doc_q.get("question", "")
                        index_question = q.get("text", "")
                        if md_question and len(md_question) > len(index_question):
                            q["text"] = md_question

                        # Use answer from markdown if not in index
                        if not q.get("answer") and doc_q.get("answer"):
                            q["answer"] = doc_q["answer"]
                        elif not q.get("answer"):
                            q["answer"] = "See study document for answer."

                        questions.append(q)

            except Exception as e:
                logger.warning(f"Could not read index for {topic_dir.name}: {e}")
                continue

        # Shuffle before returning — weighted selection in StudyHandler handles priority
        import random
        random.shuffle(questions)

        logger.info(f"Found {len(questions)} due questions for user {user_id}" +
                    (f" (topic: {topic_filter})" if topic_filter else ""))
        return questions

    def get_available_topics(self, user_id: str) -> List[str]:
        """Get list of available topics for a user"""
        learner_path = self.base_path / self._user_folder(user_id)
        topics_path = learner_path / "topics"

        if not topics_path.exists():
            return []

        topics = []
        for topic_dir in topics_path.iterdir():
            if topic_dir.is_dir() and not topic_dir.name.startswith('.'):
                topics.append(topic_dir.name)

        return sorted(topics)

    def _load_document_answers(self, topic_dir: Path) -> Dict[str, str]:
        """Load question texts and answers from study document.
        Returns dict: "filename.md#Q1" -> {"question": str, "answer": str}
        """
        doc_content = {}

        for md_file in topic_dir.glob("*.md"):
            if md_file.name.startswith('_'):
                continue

            try:
                content = md_file.read_text()
                lines = content.split('\n')
                current_q = None  # e.g. "Q1"
                q_text_parts = []

                for line in lines:
                    line_stripped = line.strip()

                    if line_stripped.startswith('**Q') and ':**' in line_stripped:
                        # Save previous question text if pending
                        if current_q and q_text_parts:
                            key = f"{md_file.name}#{current_q}"
                            doc_content.setdefault(key, {})['question'] = ' '.join(q_text_parts).strip()
                        current_q = line_stripped.split(':**')[0].replace('**', '')
                        first_line = line_stripped.split(':**', 1)[1].strip()
                        q_text_parts = [first_line] if first_line else []

                    elif line_stripped.startswith('**A') and ':**' in line_stripped and current_q:
                        # End of question text — save it
                        key = f"{md_file.name}#{current_q}"
                        if q_text_parts:
                            doc_content.setdefault(key, {})['question'] = ' '.join(q_text_parts).strip()
                        answer = line_stripped.split(':**', 1)[1].strip()
                        doc_content.setdefault(key, {})['answer'] = answer
                        current_q = None
                        q_text_parts = []

                    elif current_q and line_stripped and not line_stripped.startswith('**'):
                        # Continuation of multi-line question text
                        q_text_parts.append(line_stripped)

            except Exception as e:
                logger.warning(f"Could not parse {md_file}: {e}")

        return doc_content

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a user"""
        stats = {
            "total_questions": 0,
            "mastered": 0,
            "avg_mastery": 0,
            "total_sessions": 0,
            "due_today": 0,
            "topics": {},
            "weak_areas": []
        }

        learner_path = self.base_path / self._user_folder(user_id)
        topics_path = learner_path / "topics"
        today = date.today().isoformat()

        if not topics_path.exists():
            return stats

        all_questions = []

        for topic_dir in topics_path.iterdir():
            if not topic_dir.is_dir() or topic_dir.name.startswith('.'):
                continue

            index_path = topic_dir / "_index.yaml"
            if not index_path.exists():
                continue

            try:
                with open(index_path, 'r') as f:
                    index_data = yaml.safe_load(f)

                topic_questions = index_data.get("questions", [])
                topic_mastery = []

                for q in topic_questions:
                    q["topic"] = topic_dir.name
                    all_questions.append(q)
                    topic_mastery.append(q.get("mastery", 0))

                    if q.get("next_review") and q["next_review"] <= today:
                        stats["due_today"] += 1

                if topic_mastery:
                    stats["topics"][topic_dir.name] = {
                        "mastery": sum(topic_mastery) / len(topic_mastery),
                        "count": len(topic_mastery)
                    }

            except Exception:
                continue

        # Calculate overall stats
        stats["total_questions"] = len(all_questions)
        if all_questions:
            masteries = [q.get("mastery", 0) for q in all_questions]
            stats["avg_mastery"] = sum(masteries) / len(masteries)
            stats["mastered"] = sum(1 for m in masteries if m >= 0.8)

        # Find weak areas
        weak = {}
        for q in all_questions:
            key = (q["topic"], q.get("category", "unknown"))
            if key not in weak:
                weak[key] = []
            weak[key].append(q.get("mastery", 0))

        weak_areas = [
            {"topic": k[0], "category": k[1], "mastery": sum(v) / len(v)}
            for k, v in weak.items()
        ]
        weak_areas.sort(key=lambda x: x["mastery"])
        stats["weak_areas"] = weak_areas[:5]

        # Count sessions
        sessions_path = learner_path / "sessions"
        if sessions_path.exists():
            stats["total_sessions"] = len(list(sessions_path.glob("*.md")))

        return stats

    def save_session_results(self, user_id: str, session: Dict[str, Any]):
        """Save session results - update indexes and create session log"""
        learner_path = self.base_path / self._user_folder(user_id)
        sessions_path = learner_path / "sessions"
        sessions_path.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        session_file = sessions_path / f"{today}.md"
        counter = 2
        while session_file.exists():
            session_file = sessions_path / f"{today}-{counter}.md"
            counter += 1

        # Format session log
        content = self._format_session_log(session)

        with open(session_file, 'w') as f:
            f.write(content)

        # Update question schedules in index files
        self._update_question_schedules(learner_path, session)

        logger.info(f"Saved session for {user_id}")

    def _update_question_schedules(self, learner_path: Path, session: Dict[str, Any]):
        """Update question schedules in index files based on session results"""
        topics_path = learner_path / "topics"

        # Group results by topic
        results_by_topic = {}
        for result in session.get("results", []):
            if result.get("skipped"):
                continue
            # Skip results where grading failed
            new_schedule = result.get("new_schedule", {})
            if new_schedule.get("grading_failed"):
                logger.warning(f"Skipping schedule update for {result.get('question_id')} - grading failed")
                continue
            q_id = result.get("question_id", "")

            # Find which topic this question belongs to
            for q in session.get("questions", []):
                if q.get("id") == q_id:
                    topic = q.get("topic")
                    if topic not in results_by_topic:
                        results_by_topic[topic] = {}
                    results_by_topic[topic][q_id] = new_schedule
                    break

        # Update each topic's index
        for topic, updates in results_by_topic.items():
            index_path = topics_path / topic / "_index.yaml"
            if not index_path.exists():
                continue

            try:
                with open(index_path, 'r') as f:
                    index_data = yaml.safe_load(f)

                for q in index_data.get("questions", []):
                    if q["id"] in updates:
                        schedule = updates[q["id"]]
                        q["mastery"] = schedule.get("mastery", q.get("mastery", 0))
                        q["last_reviewed"] = schedule.get("last_reviewed")
                        q["next_review"] = schedule.get("next_review")
                        q["interval"] = schedule.get("interval", q.get("interval", 1))
                        q["easiness"] = schedule.get("easiness", q.get("easiness", 2.5))
                        q["reps"] = schedule.get("reps", q.get("reps", 0))
                        logger.info(f"Updated schedule for {q['id']}: mastery={q['mastery']}, next_review={q['next_review']}")

                index_data["last_updated"] = date.today().isoformat()

                with open(index_path, 'w') as f:
                    yaml.dump(index_data, f, default_flow_style=False, allow_unicode=True)

            except Exception as e:
                logger.error(f"Could not update index for {topic}: {e}")

    def _format_session_log(self, session: Dict[str, Any]) -> str:
        """Format session data as markdown log"""
        results = session.get("results", [])
        # Filter out skipped and None scores
        answered = [r for r in results if not r.get("skipped") and r.get("score") is not None]

        if answered:
            avg_score = sum(r["score"] for r in answered) / len(answered)
        else:
            avg_score = 0

        questions = session.get("questions", [])
        topics = list(set(q.get("topic", "unknown") for q in questions))

        content = f"""---
date: {session.get('started_at', date.today().isoformat())}
questions_reviewed: {len(results)}
topics: {topics}
average_score: {avg_score:.2f}
---

## Session Summary

- Questions: {len(results)}
- Answered: {len(answered)}
- Skipped: {len(results) - len(answered)}
- Average score: {avg_score:.1f}/5

## Questions Reviewed

| # | Question | Score |
|---|----------|-------|
"""
        for i, r in enumerate(results, 1):
            if r.get("skipped"):
                content += f"| {i} | (skipped) | - |\n"
            else:
                content += f"| {i} | {r.get('question_id', '?')} | {r.get('score', 0)}/5 |\n"

        return content

    def load_profile(self, user_id: str) -> dict:
        """Load learner profile from local file"""
        try:
            profile_path = self.base_path / self._user_folder(user_id) / "profile.yaml"
            if profile_path.exists():
                with open(profile_path, 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load profile for {user_id}: {e}")
        return {}

    def load_tutor_config(self, user_id: str) -> dict:
        """Load per-user tutor personality from tutor.yaml, or empty dict if absent."""
        try:
            path = self.base_path / self._user_folder(user_id) / "tutor.yaml"
            if path.exists():
                return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning(f"Could not load tutor config for {user_id}: {e}")
        return {}

    def save_profile(self, user_id: str, profile: dict):
        """Save learner profile to profile.yaml"""
        learner_path = self.base_path / self._user_folder(user_id)
        learner_path.mkdir(parents=True, exist_ok=True)
        profile_path = learner_path / "profile.yaml"

        with open(profile_path, 'w') as f:
            yaml.dump(profile, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Saved profile for {user_id} to {profile_path}")

    def save_study_guide(self, user_id: str, date: str, content: str):
        """Save a post-session study guide to local file."""
        guides_path = self.base_path / self._user_folder(user_id) / "study-guides"
        guides_path.mkdir(parents=True, exist_ok=True)
        with open(guides_path / f"{date}.md", 'w') as f:
            f.write(content)
        logger.info(f"Saved study guide for {user_id}")

    def load_memory(self, user_id: str) -> dict:
        """Load the learner's memory.yaml file."""
        try:
            learner_path = self.base_path / self._user_folder(user_id)
            memory_path = learner_path / "memory.yaml"
            if memory_path.exists():
                with open(memory_path, 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load memory for {user_id}: {e}")
        return {}

    def save_memory(self, user_id: str, memory: dict):
        """Save the learner's memory.yaml file."""
        try:
            learner_path = self.base_path / self._user_folder(user_id)
            learner_path.mkdir(parents=True, exist_ok=True)
            memory_path = learner_path / "memory.yaml"
            with open(memory_path, 'w') as f:
                yaml.dump(memory, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Could not save memory for {user_id}: {e}")
            raise

    def save_onboarding_state(self, user_id: str, state: dict):
        """Persist onboarding state so it survives bot restarts."""
        learner_path = self.base_path / self._user_folder(user_id)
        learner_path.mkdir(parents=True, exist_ok=True)
        with open(learner_path / "onboarding_state.yaml", 'w') as f:
            yaml.dump(state, f, default_flow_style=False, allow_unicode=True)

    def load_onboarding_state(self, user_id: str) -> dict:
        """Load persisted onboarding state, or empty dict if none."""
        try:
            path = self.base_path / self._user_folder(user_id) / "onboarding_state.yaml"
            if path.exists():
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load onboarding state for {user_id}: {e}")
        return {}

    def clear_onboarding_state(self, user_id: str):
        """Delete persisted onboarding state after completion or cancellation."""
        try:
            path = self.base_path / self._user_folder(user_id) / "onboarding_state.yaml"
            path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Could not clear onboarding state for {user_id}: {e}")

    def save_pending_upload_state(self, user_id: str, state: dict):
        """Persist pending upload confirmation state so it survives restarts."""
        learner_path = self.base_path / self._user_folder(user_id)
        learner_path.mkdir(parents=True, exist_ok=True)
        with open(learner_path / "pending_upload.yaml", 'w') as f:
            yaml.dump(state, f, default_flow_style=False, allow_unicode=True)

    def load_pending_upload_state(self, user_id: str) -> dict:
        """Load pending upload confirmation state, or empty dict if none."""
        try:
            path = self.base_path / self._user_folder(user_id) / "pending_upload.yaml"
            if path.exists():
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load pending upload state for {user_id}: {e}")
        return {}

    def clear_pending_upload_state(self, user_id: str):
        """Delete persisted pending upload state after completion or cancellation."""
        try:
            path = self.base_path / self._user_folder(user_id) / "pending_upload.yaml"
            path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Could not clear pending upload state for {user_id}: {e}")

    def save_recent_task_state(self, user_id: str, state: dict):
        """Persist lightweight recent conversational task state."""
        learner_path = self.base_path / self._user_folder(user_id)
        learner_path.mkdir(parents=True, exist_ok=True)
        with open(learner_path / "recent_task_state.yaml", 'w') as f:
            yaml.dump(state, f, default_flow_style=False, allow_unicode=True)

    def load_recent_task_state(self, user_id: str) -> dict:
        """Load recent conversational task state, or empty dict if none."""
        try:
            path = self.base_path / self._user_folder(user_id) / "recent_task_state.yaml"
            if path.exists():
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load recent task state for {user_id}: {e}")
        return {}

    def clear_recent_task_state(self, user_id: str):
        """Delete recent conversational task state."""
        try:
            path = self.base_path / self._user_folder(user_id) / "recent_task_state.yaml"
            path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Could not clear recent task state for {user_id}: {e}")

    # ── Curriculum ────────────────────────────────────────────────────────────

    def save_curriculum_state(self, user_id: str, state: dict):
        """Persist in-progress curriculum conversation state."""
        learner_path = self.base_path / self._user_folder(user_id)
        learner_path.mkdir(parents=True, exist_ok=True)
        with open(learner_path / "curriculum_state.yaml", 'w') as f:
            yaml.dump(state, f, default_flow_style=False, allow_unicode=True)

    def load_curriculum_state(self, user_id: str) -> dict:
        """Load persisted curriculum conversation state, or empty dict."""
        try:
            path = self.base_path / self._user_folder(user_id) / "curriculum_state.yaml"
            if path.exists():
                return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning(f"Could not load curriculum state for {user_id}: {e}")
        return {}

    def clear_curriculum_state(self, user_id: str):
        """Delete curriculum conversation state."""
        try:
            path = self.base_path / self._user_folder(user_id) / "curriculum_state.yaml"
            path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Could not clear curriculum state for {user_id}: {e}")

    def save_curriculum_plan(self, user_id: str, curriculum_id: str, plan: dict):
        """Write plan.yaml for a curriculum."""
        plan_path = self.base_path / self._user_folder(user_id) / "curricula" / curriculum_id
        plan_path.mkdir(parents=True, exist_ok=True)
        (plan_path / "plan.yaml").write_text(
            yaml.dump(plan, default_flow_style=False, allow_unicode=True),
            encoding="utf-8"
        )

    def load_curriculum_plan(self, user_id: str, curriculum_id: str) -> dict:
        """Load plan.yaml for a curriculum."""
        try:
            path = self.base_path / self._user_folder(user_id) / "curricula" / curriculum_id / "plan.yaml"
            if path.exists():
                return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning(f"Could not load curriculum plan {curriculum_id} for {user_id}: {e}")
        return {}

    def get_active_curriculum_id(self, user_id: str) -> str:
        """Return the curriculum_id of the user's active curriculum, or empty string."""
        try:
            curricula_path = self.base_path / self._user_folder(user_id) / "curricula"
            if not curricula_path.exists():
                return ""
            for plan_file in curricula_path.glob("*/plan.yaml"):
                try:
                    plan = yaml.safe_load(plan_file.read_text(encoding="utf-8")) or {}
                    if plan.get("status") == "active":
                        return plan.get("id", "")
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Could not scan curricula for {user_id}: {e}")
        return ""

    def save_conversation(self, user_id: str, messages: list):
        """Persist conversation buffer to disk so it survives restarts."""
        try:
            learner_path = self.base_path / self._user_folder(user_id)
            learner_path.mkdir(parents=True, exist_ok=True)
            path = learner_path / "conversation.yaml"
            with open(path, 'w') as f:
                yaml.dump({"messages": messages}, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.warning(f"Could not save conversation for {user_id}: {e}")

    def load_conversation(self, user_id: str) -> list:
        """Load persisted conversation buffer, or empty list if none."""
        try:
            path = self.base_path / self._user_folder(user_id) / "conversation.yaml"
            if path.exists():
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                return data.get("messages", [])
        except Exception as e:
            logger.warning(f"Could not load conversation for {user_id}: {e}")
        return []

    def _user_folder(self, user_id: str) -> str:
        """Convert Slack user ID to folder name by reading learners/user_map.yaml"""
        try:
            map_path = self.base_path / "user_map.yaml"
            if map_path.exists():
                with open(map_path, 'r') as f:
                    user_map = yaml.safe_load(f) or {}
                return user_map.get(user_id, user_id)
        except Exception as e:
            logger.warning(f"Could not read user_map.yaml: {e}")
        return user_id

    def save_study_document(self, user_id: str, topic: str, doc_name: str, content: str):
        """Save a study document .md file to a topic folder."""
        topic_path = self.base_path / self._user_folder(user_id) / "topics" / topic
        topic_path.mkdir(parents=True, exist_ok=True)
        (topic_path / f"{doc_name}.md").write_text(content, encoding="utf-8")
        logger.info(f"Saved study document {topic}/{doc_name}.md for {user_id}")

    def delete_study_document(self, user_id: str, topic: str, doc_name: str):
        """Delete one topic-scoped compatibility study document."""
        filename = doc_name if doc_name.endswith(".md") else f"{doc_name}.md"
        path = self.base_path / self._user_folder(user_id) / "topics" / topic / filename
        try:
            path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Could not delete study document {topic}/{filename} for {user_id}: {e}")

    def rename_topic_folder(self, user_id: str, old_name: str, new_name: str) -> bool:
        """Rename a topic folder on disk. Returns True if successful."""
        topics_root = self.base_path / self._user_folder(user_id) / "topics"
        old_path = topics_root / old_name
        new_path = topics_root / new_name
        if not old_path.exists():
            logger.warning(f"rename_topic_folder: {old_path} does not exist")
            return False
        if new_path.exists():
            logger.warning(f"rename_topic_folder: target {new_path} already exists")
            return False
        try:
            old_path.rename(new_path)
            logger.info(f"Renamed topic folder {old_name} → {new_name} for {user_id}")
            return True
        except Exception as e:
            logger.warning(f"Could not rename topic folder {old_name} for {user_id}: {e}")
            return False

    def delete_topic_folder(self, user_id: str, topic: str):
        """Delete the entire topic folder and all its files from disk."""
        import shutil
        topic_path = self.base_path / self._user_folder(user_id) / "topics" / topic
        if not topic_path.exists():
            logger.info(f"delete_topic_folder: {topic_path} does not exist, nothing to remove")
            return
        try:
            shutil.rmtree(topic_path)
            logger.info(f"Deleted topic folder {topic} for {user_id}")
        except Exception as e:
            logger.warning(f"Could not delete topic folder {topic} for {user_id}: {e}")

    def save_document_bundle(
        self,
        user_id: str,
        manifest: dict,
        source_content: str,
        notes_content: str,
        questions: list,
        merge_manifest: bool = True,
    ):
        """Persist the canonical per-document bundle."""
        document_path = self._document_path(user_id, manifest.get("doc_id", ""))
        document_path.mkdir(parents=True, exist_ok=True)

        existing = self.get_document_manifest(user_id, manifest.get("doc_id", "")) if merge_manifest else {}
        merged_manifest = self._merge_document_manifest(existing, manifest) if merge_manifest else manifest

        (document_path / "manifest.yaml").write_text(
            yaml.dump(merged_manifest, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        (document_path / "source.md").write_text(source_content or "", encoding="utf-8")
        (document_path / "notes.md").write_text(notes_content or "", encoding="utf-8")
        (document_path / "questions.yaml").write_text(
            yaml.dump({"questions": questions or []}, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

    def get_document_manifest(self, user_id: str, doc_id: str) -> dict:
        """Load one document manifest, or return empty dict."""
        if not doc_id:
            return {}
        path = self._document_path(user_id, doc_id) / "manifest.yaml"
        if not path.exists():
            return {}
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def get_document_source(self, user_id: str, doc_id: str) -> str:
        """Load the canonical source markdown for one document."""
        if not doc_id:
            return ""
        path = self._document_path(user_id, doc_id) / "source.md"
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def get_document_notes(self, user_id: str, doc_id: str) -> str:
        """Load the canonical learner-facing notes for one document."""
        if not doc_id:
            return ""
        path = self._document_path(user_id, doc_id) / "notes.md"
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def get_document_questions(self, user_id: str, doc_id: str) -> List[Dict[str, Any]]:
        """Load the canonical question list for one document."""
        if not doc_id:
            return []
        path = self._document_path(user_id, doc_id) / "questions.yaml"
        if not path.exists():
            return []
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return list(data.get("questions", []) or [])
        except Exception:
            return []

    def list_document_manifests(self, user_id: str) -> List[dict]:
        """Load all known document manifests for one learner."""
        documents_path = self.base_path / self._user_folder(user_id) / "documents"
        if not documents_path.exists():
            return []
        manifests = []
        for item in sorted(documents_path.iterdir()):
            if not item.is_dir():
                continue
            manifest = self.get_document_manifest(user_id, item.name)
            if manifest:
                manifests.append(manifest)
        return manifests

    def get_topic_document_manifests(self, user_id: str, topic: str) -> List[dict]:
        """Return manifests whose classification includes the requested topic."""
        topic_lower = topic.lower().strip()
        return [
            manifest
            for manifest in self.list_document_manifests(user_id)
            if topic_lower in {
                str(item).lower().strip()
                for item in ((manifest.get("classification") or {}).get("topics", []) or [])
            }
        ]

    def study_document_exists(self, user_id: str, topic: str, doc_name: str) -> bool:
        """Return True when the exact study document already exists."""
        path = self.base_path / self._user_folder(user_id) / "topics" / topic / f"{doc_name}.md"
        return path.exists()

    def get_study_document_content(self, user_id: str, topic: str, doc_name: str) -> str:
        """Load the raw topic-scoped markdown study document."""
        filename = doc_name if doc_name.endswith(".md") else f"{doc_name}.md"
        path = self.base_path / self._user_folder(user_id) / "topics" / topic / filename
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def list_topic_documents(self, user_id: str, topic: str) -> List[str]:
        """Return Markdown study documents in a topic folder."""
        topic_path = self.base_path / self._user_folder(user_id) / "topics" / topic
        if not topic_path.exists():
            return []
        return sorted(
            path.name
            for path in topic_path.glob("*.md")
            if not path.name.startswith("_")
        )

    def get_study_document_notes(self, user_id: str, topic: str, doc_name: str) -> str:
        """Load notes from one exact study document."""
        filename = doc_name if doc_name.endswith(".md") else f"{doc_name}.md"
        path = self.base_path / self._user_folder(user_id) / "topics" / topic / filename
        if not path.exists():
            return ""
        try:
            return self._extract_notes_section(path.read_text(encoding="utf-8"))
        except Exception:
            return ""

    def get_topic_index(self, user_id: str, topic: str) -> dict:
        """Load _index.yaml for a topic, or return empty structure."""
        index_path = self.base_path / self._user_folder(user_id) / "topics" / topic / "_index.yaml"
        if not index_path.exists():
            return {}
        try:
            return yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def update_topic_index(self, user_id: str, topic: str, index_data: dict):
        """Write _index.yaml for a topic."""
        topic_path = self.base_path / self._user_folder(user_id) / "topics" / topic
        topic_path.mkdir(parents=True, exist_ok=True)
        index_path = topic_path / "_index.yaml"
        index_path.write_text(
            yaml.dump(index_data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8"
        )
        logger.info(f"Updated index for {user_id}/{topic}")

    # ── RAG: study note retrieval ─────────────────────────────────────────────

    def get_topic_notes(self, user_id: str, topic: str) -> str:
        """
        Load the notes section from all study docs in a topic folder.
        Returns everything above '## Anki Questions' in each .md file.
        """
        topic_folder = self.base_path / self._user_folder(user_id) / "topics" / topic
        if not topic_folder.exists():
            return ""

        parts = []
        for md_file in sorted(topic_folder.glob("*.md")):
            if md_file.name.startswith("_"):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                notes = self._extract_notes_section(content)
                if notes:
                    parts.append(f"### {md_file.stem}\n{notes}")
            except Exception:
                continue

        return "\n\n".join(parts)

    def _extract_notes_section(self, content: str) -> str:
        """Return study notes without frontmatter or Anki questions."""
        notes = content.split("## Anki Questions")[0].strip() if "## Anki Questions" in content else content.strip()
        if notes.startswith("---"):
            frontmatter_parts = notes.split("---", 2)
            if len(frontmatter_parts) >= 3:
                notes = frontmatter_parts[2].strip()
        return notes

    def search_topics_by_keyword(self, user_id: str, query: str) -> str:
        """
        Find the topic whose name and content best match keywords in query.
        Returns the notes from the best-matching topic, or empty string.
        """
        topics_dir = self.base_path / self._user_folder(user_id) / "topics"
        if not topics_dir.exists():
            return ""

        stop_words = {
            "what", "how", "why", "can", "you", "that", "this", "about", "more",
            "help", "understand", "tell", "explain", "does", "mean", "from", "with",
            "have", "been", "also", "some", "just", "like", "when", "there", "then"
        }
        query_words = {w for w in query.lower().split() if len(w) > 3 and w not in stop_words}
        if not query_words:
            return ""

        best_topic = None
        best_score = 0

        for topic_dir in topics_dir.iterdir():
            if not topic_dir.is_dir():
                continue
            topic_name = topic_dir.name.replace("-", " ").replace("_", " ").lower()
            # Name matches weighted 3x — topic name is a strong signal
            score = sum(3 for w in query_words if w in topic_name)
            # Content matches in first 3000 chars of each doc
            for md_file in topic_dir.glob("*.md"):
                if md_file.name.startswith("_"):
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8")[:3000].lower()
                    score += sum(1 for w in query_words if w in content)
                except Exception:
                    continue
            if score > best_score:
                best_score = score
                best_topic = topic_dir.name

        if best_topic and best_score > 0:
            notes = self.get_topic_notes(user_id, best_topic)
            logger.info(f"RAG: matched topic '{best_topic}' (score={best_score}) for: {query[:60]}")
            return notes

        return ""

    def _document_path(self, user_id: str, doc_id: str) -> Path:
        """Return the canonical storage path for one document bundle."""
        return self.base_path / self._user_folder(user_id) / "documents" / doc_id

    def _merge_document_manifest(self, existing: dict, new: dict) -> dict:
        """Merge topic memberships and preserve existing timestamps when rewriting."""
        if not existing:
            return copy.deepcopy(new)

        merged = copy.deepcopy(existing)
        merged.update(copy.deepcopy(new))
        merged["created_at"] = existing.get("created_at", new.get("created_at", ""))

        existing_topics = list((((existing.get("classification") or {}).get("topics")) or []))
        new_topics = list((((new.get("classification") or {}).get("topics")) or []))
        merged.setdefault("classification", {})
        merged["classification"]["topics"] = list(dict.fromkeys(existing_topics + new_topics))

        existing_memberships = list((((existing.get("storage") or {}).get("topic_memberships")) or []))
        new_memberships = list((((new.get("storage") or {}).get("topic_memberships")) or []))
        merged.setdefault("storage", {})
        merged["storage"]["topic_memberships"] = list(dict.fromkeys(existing_memberships + new_memberships))
        merged["updated_at"] = new.get("updated_at", existing.get("updated_at", ""))
        return merged

"""
GitLab Service
Reads and writes learner data from GitLab repos
"""

import os
import logging
import copy
import yaml
from datetime import date, datetime
from typing import List, Dict, Any, Optional
import gitlab

logger = logging.getLogger(__name__)


class GitLabService:
    """Manages GitLab operations for learner repos"""

    def __init__(self):
        self.gl = gitlab.Gitlab(
            url=os.getenv("GITLAB_URL", "https://gitlab.com"),
            private_token=os.getenv("GITLAB_ACCESS_TOKEN")
        )
        self.gl.auth()

        # GitLab project path containing all learner data
        self.base_project = os.getenv(
            "GITLAB_LEARNERS_PROJECT",
            "the-smithy1/agents/sofi"
        )
        self.learners_path = "learners"
        self.branch = os.getenv("GITLAB_LEARNERS_BRANCH", "main")

    def get_due_questions(self, user_id: str, topic_filter: str = None) -> List[Dict[str, Any]]:
        """Get all questions due for review for a user, optionally filtered by topic"""
        questions = []
        today = date.today().isoformat()

        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"

            # Get all topic folders
            topics = self._list_folders(project, f"{learner_path}/topics")

            for topic in topics:
                # Apply topic filter if specified
                if topic_filter:
                    if topic_filter.lower() not in topic.lower():
                        continue

                index_path = f"{learner_path}/topics/{topic}/_index.yaml"
                try:
                    index_content = self._read_file(project, index_path)
                    index_data = yaml.safe_load(index_content)

                    # Load answers from study doc
                    doc_questions = self._load_document_answers(project, learner_path, topic)

                    for q in index_data.get("questions", []):
                        next_review = q.get("next_review")
                        if next_review is None or next_review <= today:
                            q["topic"] = topic
                            doc_q = doc_questions.get(q["id"], {})
                            if not q.get("answer") and doc_q.get("answer"):
                                q["answer"] = doc_q["answer"]
                            elif not q.get("answer"):
                                q["answer"] = "See study document for answer."
                            if doc_q.get("question") and len(doc_q["question"]) > len(q.get("text", "")):
                                q["text"] = doc_q["question"]
                            questions.append(q)

                except Exception as e:
                    logger.warning(f"Could not read index for {topic}: {e}")
                    continue

            # Sort by mastery (lowest first) then by last_reviewed (oldest first)
            questions.sort(key=lambda q: (
                q.get("mastery", 0),
                q.get("last_reviewed") or "1900-01-01"
            ))

            logger.info(f"Found {len(questions)} due questions for user {user_id}" +
                        (f" (topic: {topic_filter})" if topic_filter else ""))
            return questions

        except Exception as e:
            logger.error(f"Error getting due questions: {e}")
            return []

    def get_available_topics(self, user_id: str) -> List[str]:
        """Get list of available topics for a user"""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            topics = self._list_folders(project, f"{learner_path}/topics")
            return sorted(topics)
        except Exception as e:
            logger.error(f"Error getting topics: {e}")
            return []

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

        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            today = date.today().isoformat()

            topics = self._list_folders(project, f"{learner_path}/topics")
            all_questions = []

            for topic in topics:
                index_path = f"{learner_path}/topics/{topic}/_index.yaml"
                try:
                    index_content = self._read_file(project, index_path)
                    index_data = yaml.safe_load(index_content)

                    topic_questions = index_data.get("questions", [])
                    topic_mastery = []

                    for q in topic_questions:
                        q["topic"] = topic
                        all_questions.append(q)
                        topic_mastery.append(q.get("mastery", 0))

                        if q.get("next_review") and q["next_review"] <= today:
                            stats["due_today"] += 1

                    if topic_mastery:
                        stats["topics"][topic] = {
                            "mastery": sum(topic_mastery) / len(topic_mastery),
                            "count": len(topic_mastery)
                        }

                except Exception:
                    continue

            stats["total_questions"] = len(all_questions)
            if all_questions:
                masteries = [q.get("mastery", 0) for q in all_questions]
                stats["avg_mastery"] = sum(masteries) / len(masteries)
                stats["mastered"] = sum(1 for m in masteries if m >= 0.8)

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

            try:
                sessions = self._list_files(project, f"{learner_path}/sessions")
                stats["total_sessions"] = len(sessions)
            except Exception:
                pass

            return stats

        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return stats

    def save_session_results(self, user_id: str, session: Dict[str, Any]):
        """Save session results - update indexes and create session log"""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            today = date.today().isoformat()

            # Save session log — avoid overwriting if multiple sessions on same day
            session_content = self._format_session_log(session)
            existing = self._list_files(project, f"{learner_path}/sessions")
            session_filename = f"{today}.md"
            counter = 2
            while session_filename in existing:
                session_filename = f"{today}-{counter}.md"
                counter += 1
            session_path = f"{learner_path}/sessions/{session_filename}"
            self._write_file(project, session_path, session_content)

            # Update question schedules in index files (grouped by topic)
            results_by_topic = {}
            for result in session.get("results", []):
                if result.get("skipped"):
                    continue
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

            # Update each topic's index on GitLab
            for topic, updates in results_by_topic.items():
                if not topic:
                    continue
                index_path = f"{learner_path}/topics/{topic}/_index.yaml"
                try:
                    index_content = self._read_file(project, index_path)
                    index_data = yaml.safe_load(index_content)

                    for q in index_data.get("questions", []):
                        if q["id"] in updates:
                            schedule = updates[q["id"]]
                            q["mastery"] = schedule.get("mastery", q.get("mastery", 0))
                            q["last_reviewed"] = schedule.get("last_reviewed")
                            q["next_review"] = schedule.get("next_review")
                            q["interval"] = schedule.get("interval", q.get("interval", 1))
                            q["easiness"] = schedule.get("easiness", q.get("easiness", 2.5))
                            q["reps"] = schedule.get("reps", q.get("reps", 0))
                            logger.info(f"Updated {q['id']}: mastery={q['mastery']}, next_review={q['next_review']}")

                    index_data["last_updated"] = today
                    updated_content = yaml.dump(index_data, default_flow_style=False, allow_unicode=True)
                    self._write_file(project, index_path, updated_content)

                except Exception as e:
                    logger.error(f"Could not update index for {topic}: {e}")

            logger.info(f"Saved session for {user_id}")

        except Exception as e:
            logger.error(f"Error saving session: {e}")
            raise

    def _load_document_answers(self, project, learner_path: str, topic: str) -> Dict[str, dict]:
        """Load Q&A pairs from study documents in GitLab.
        Returns dict: "filename.md#Q1" -> {"question": str, "answer": str}
        """
        doc_content = {}
        try:
            files = self._list_files(project, f"{learner_path}/topics/{topic}")
            for filename in files:
                if not filename.endswith(".md") or filename.startswith("_"):
                    continue
                content = self._read_file(project, f"{learner_path}/topics/{topic}/{filename}")
                lines = content.split('\n')
                current_q = None
                q_text_parts = []
                for line in lines:
                    line = line.strip()
                    if line.startswith('**Q') and ':**' in line:
                        if current_q and q_text_parts:
                            key = f"{filename}#{current_q}"
                            doc_content.setdefault(key, {})['question'] = ' '.join(q_text_parts).strip()
                        current_q = line.split(':**')[0].replace('**', '')
                        first_line = line.split(':**', 1)[1].strip()
                        q_text_parts = [first_line] if first_line else []
                    elif line.startswith('**A') and ':**' in line and current_q:
                        key = f"{filename}#{current_q}"
                        if q_text_parts:
                            doc_content.setdefault(key, {})['question'] = ' '.join(q_text_parts).strip()
                        doc_content.setdefault(key, {})['answer'] = line.split(':**', 1)[1].strip()
                        current_q = None
                        q_text_parts = []
                    elif current_q and line and not line.startswith('**'):
                        q_text_parts.append(line)
        except Exception as e:
            logger.warning(f"Could not load answers for {topic}: {e}")
        return doc_content

    def _format_session_log(self, session: Dict[str, Any]) -> str:
        """Format session data as markdown log"""
        results = session.get("results", [])
        answered = [r for r in results if not r.get("skipped") and r.get("score") is not None]

        avg_score = sum(r["score"] for r in answered) / len(answered) if answered else 0
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

    def _user_folder(self, user_id: str) -> str:
        """Convert Slack user ID to folder name via user_map.yaml in GitLab"""
        try:
            project = self.gl.projects.get(self.base_project)
            content = self._read_file(project, f"{self.learners_path}/user_map.yaml")
            user_map = yaml.safe_load(content) or {}
            return user_map.get(user_id, user_id)
        except Exception as e:
            logger.warning(f"Could not load user_map.yaml: {e}")
            return user_id

    def load_profile(self, user_id: str) -> dict:
        """Load learner profile from GitLab"""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = self._read_file(project, f"{learner_path}/profile.yaml")
            return yaml.safe_load(content) or {}
        except Exception as e:
            logger.warning(f"Could not load profile for {user_id}: {e}")
            return {}

    def save_profile(self, user_id: str, profile: dict):
        """Save learner profile to GitLab"""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = yaml.dump(profile, default_flow_style=False, allow_unicode=True)
            self._write_file(project, f"{learner_path}/profile.yaml", content)
            logger.info(f"Saved profile for {user_id}")
        except Exception as e:
            logger.error(f"Could not save profile for {user_id}: {e}")
            raise

    def save_study_document(self, user_id: str, topic: str, doc_name: str, content: str):
        """Save a study document .md file to a topic folder."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            path = f"{learner_path}/topics/{topic}/{doc_name}.md"
            self._write_file(project, path, content)
            logger.info(f"Saved study document {path}")
        except Exception as e:
            logger.error(f"Could not save study document for {user_id}: {e}")
            raise

    def delete_study_document(self, user_id: str, topic: str, doc_name: str):
        """Delete one topic-scoped compatibility study document."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            filename = doc_name if doc_name.endswith(".md") else f"{doc_name}.md"
            project.files.delete(
                file_path=f"{learner_path}/topics/{topic}/{filename}",
                branch=self.branch,
                commit_message=f"Delete topics/{topic}/{filename}",
            )
        except Exception:
            pass

    def save_document_bundle(
        self,
        user_id: str,
        manifest: dict,
        source_content: str,
        notes_content: str,
        questions: list,
        merge_manifest: bool = True,
    ):
        """Persist the canonical per-document bundle to GitLab."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            doc_id = manifest.get("doc_id", "")
            base = f"{learner_path}/documents/{doc_id}"
            existing = self.get_document_manifest(user_id, doc_id) if merge_manifest else {}
            merged_manifest = self._merge_document_manifest(existing, manifest) if merge_manifest else manifest
            self._write_file(
                project,
                f"{base}/manifest.yaml",
                yaml.dump(merged_manifest, default_flow_style=False, allow_unicode=True),
            )
            self._write_file(project, f"{base}/source.md", source_content or "")
            self._write_file(project, f"{base}/notes.md", notes_content or "")
            self._write_file(
                project,
                f"{base}/questions.yaml",
                yaml.dump({"questions": questions or []}, default_flow_style=False, allow_unicode=True),
            )
        except Exception as e:
            logger.error(f"Could not save document bundle for {user_id}: {e}")
            raise

    def get_document_manifest(self, user_id: str, doc_id: str) -> dict:
        """Load one document manifest from GitLab, or return empty dict."""
        try:
            if not doc_id:
                return {}
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = self._read_file(project, f"{learner_path}/documents/{doc_id}/manifest.yaml")
            return yaml.safe_load(content) or {}
        except Exception:
            return {}

    def get_document_source(self, user_id: str, doc_id: str) -> str:
        """Load the canonical source markdown for one document."""
        try:
            if not doc_id:
                return ""
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            return self._read_file(project, f"{learner_path}/documents/{doc_id}/source.md")
        except Exception:
            return ""

    def get_document_notes(self, user_id: str, doc_id: str) -> str:
        """Load the canonical learner-facing notes for one document."""
        try:
            if not doc_id:
                return ""
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            return self._read_file(project, f"{learner_path}/documents/{doc_id}/notes.md")
        except Exception:
            return ""

    def get_document_questions(self, user_id: str, doc_id: str) -> List[Dict[str, Any]]:
        """Load the canonical question list for one document."""
        try:
            if not doc_id:
                return []
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = self._read_file(project, f"{learner_path}/documents/{doc_id}/questions.yaml")
            data = yaml.safe_load(content) or {}
            return list(data.get("questions", []) or [])
        except Exception:
            return []

    def list_document_manifests(self, user_id: str) -> List[dict]:
        """List all document manifests for a learner."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            doc_ids = self._list_folders(project, f"{learner_path}/documents")
            manifests = []
            for doc_id in sorted(doc_ids):
                manifest = self.get_document_manifest(user_id, doc_id)
                if manifest:
                    manifests.append(manifest)
            return manifests
        except Exception:
            return []

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
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            path = f"{learner_path}/topics/{topic}/{doc_name}.md"
            project.files.get(file_path=path, ref=self.branch)
            return True
        except Exception:
            return False

    def get_study_document_content(self, user_id: str, topic: str, doc_name: str) -> str:
        """Load the raw topic-scoped markdown study document."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            filename = doc_name if doc_name.endswith(".md") else f"{doc_name}.md"
            return self._read_file(project, f"{learner_path}/topics/{topic}/{filename}")
        except Exception:
            return ""

    def list_topic_documents(self, user_id: str, topic: str) -> List[str]:
        """Return Markdown study documents in a topic folder."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            topic_path = f"{learner_path}/topics/{topic}"
            return sorted(
                filename
                for filename in self._list_files(project, topic_path)
                if filename.endswith(".md") and not filename.startswith("_")
            )
        except Exception:
            return []

    def get_study_document_notes(self, user_id: str, topic: str, doc_name: str) -> str:
        """Load notes from one exact study document."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            filename = doc_name if doc_name.endswith(".md") else f"{doc_name}.md"
            path = f"{learner_path}/topics/{topic}/{filename}"
            content = self._read_file(project, path)
            return self._extract_notes_section(content)
        except Exception:
            return ""

    def get_topic_index(self, user_id: str, topic: str) -> dict:
        """Load _index.yaml for a topic, or return empty structure."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = self._read_file(project, f"{learner_path}/topics/{topic}/_index.yaml")
            return yaml.safe_load(content) or {}
        except Exception:
            return {}

    def update_topic_index(self, user_id: str, topic: str, index_data: dict):
        """Write _index.yaml for a topic."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = yaml.dump(index_data, default_flow_style=False, allow_unicode=True)
            self._write_file(project, f"{learner_path}/topics/{topic}/_index.yaml", content)
            logger.info(f"Updated index for {user_id}/{topic}")
        except Exception as e:
            logger.error(f"Could not update topic index for {user_id}/{topic}: {e}")
            raise

    def save_study_guide(self, user_id: str, date: str, content: str):
        """Save a post-session study guide to GitLab."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            self._write_file(project, f"{learner_path}/study-guides/{date}.md", content)
            logger.info(f"Saved study guide for {user_id}")
        except Exception as e:
            logger.error(f"Could not save study guide for {user_id}: {e}")
            raise

    def get_topic_notes(self, user_id: str, topic: str) -> str:
        """Load the notes section from all study docs in a topic folder."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            topic_path = f"{learner_path}/topics/{topic}"
            files = self._list_files(project, topic_path)

            parts = []
            for filename in sorted(files):
                if not filename.endswith(".md") or filename.startswith("_"):
                    continue
                try:
                    content = self._read_file(project, f"{topic_path}/{filename}")
                    notes = self._extract_notes_section(content)
                    stem = filename.replace(".md", "")
                    if notes:
                        parts.append(f"### {stem}\n{notes}")
                except Exception:
                    continue

            return "\n\n".join(parts)
        except Exception as e:
            logger.warning(f"Could not load topic notes for {user_id}/{topic}: {e}")
            return ""

    def _extract_notes_section(self, content: str) -> str:
        """Return study notes without frontmatter or Anki questions."""
        notes = (
            content.split("## Anki Questions")[0].strip()
            if "## Anki Questions" in content else content.strip()
        )
        if notes.startswith("---"):
            parts_split = notes.split("---", 2)
            if len(parts_split) >= 3:
                notes = parts_split[2].strip()
        return notes

    def load_memory(self, user_id: str) -> dict:
        """Load learner memory.yaml from GitLab"""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = self._read_file(project, f"{learner_path}/memory.yaml")
            return yaml.safe_load(content) or {}
        except Exception as e:
            logger.warning(f"Could not load memory for {user_id}: {e}")
            return {}

    def save_memory(self, user_id: str, memory: dict):
        """Save learner memory.yaml to GitLab"""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = yaml.dump(memory, default_flow_style=False, allow_unicode=True)
            self._write_file(project, f"{learner_path}/memory.yaml", content)
        except Exception as e:
            logger.error(f"Could not save memory for {user_id}: {e}")
            raise

    def save_onboarding_state(self, user_id: str, state: dict):
        """Save onboarding state to GitLab"""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = yaml.dump(state, default_flow_style=False, allow_unicode=True)
            self._write_file(project, f"{learner_path}/onboarding_state.yaml", content)
        except Exception as e:
            logger.warning(f"Could not save onboarding state for {user_id}: {e}")

    def load_onboarding_state(self, user_id: str) -> dict:
        """Load onboarding state from GitLab"""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = self._read_file(project, f"{learner_path}/onboarding_state.yaml")
            return yaml.safe_load(content) or {}
        except Exception:
            return {}

    def clear_onboarding_state(self, user_id: str):
        """Delete onboarding state from GitLab"""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            project.files.delete(
                file_path=f"{learner_path}/onboarding_state.yaml",
                branch=self.branch,
                commit_message="Clear onboarding state"
            )
        except Exception:
            pass  # File may not exist, that's fine

    def save_pending_upload_state(self, user_id: str, state: dict):
        """Save pending upload confirmation state to GitLab."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = yaml.dump(state, default_flow_style=False, allow_unicode=True)
            self._write_file(project, f"{learner_path}/pending_upload.yaml", content)
        except Exception as e:
            logger.warning(f"Could not save pending upload state for {user_id}: {e}")

    def load_pending_upload_state(self, user_id: str) -> dict:
        """Load pending upload confirmation state from GitLab."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = self._read_file(project, f"{learner_path}/pending_upload.yaml")
            return yaml.safe_load(content) or {}
        except Exception:
            return {}

    def clear_pending_upload_state(self, user_id: str):
        """Delete pending upload confirmation state from GitLab."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            project.files.delete(
                file_path=f"{learner_path}/pending_upload.yaml",
                branch=self.branch,
                commit_message="Clear pending upload state"
            )
        except Exception:
            pass

    def save_recent_task_state(self, user_id: str, state: dict):
        """Save lightweight recent conversational task state to GitLab."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = yaml.dump(state, default_flow_style=False, allow_unicode=True)
            self._write_file(project, f"{learner_path}/recent_task_state.yaml", content)
        except Exception as e:
            logger.warning(f"Could not save recent task state for {user_id}: {e}")

    def load_recent_task_state(self, user_id: str) -> dict:
        """Load lightweight recent conversational task state from GitLab."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = self._read_file(project, f"{learner_path}/recent_task_state.yaml")
            return yaml.safe_load(content) or {}
        except Exception:
            return {}

    def clear_recent_task_state(self, user_id: str):
        """Delete recent conversational task state from GitLab."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            project.files.delete(
                file_path=f"{learner_path}/recent_task_state.yaml",
                branch=self.branch,
                commit_message="Clear recent task state"
            )
        except Exception:
            pass

    def save_conversation(self, user_id: str, messages: list):
        """Persist conversation buffer to GitLab."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = yaml.dump({"messages": messages}, default_flow_style=False, allow_unicode=True)
            self._write_file(project, f"{learner_path}/conversation.yaml", content)
        except Exception as e:
            logger.warning(f"Could not save conversation for {user_id}: {e}")

    def load_conversation(self, user_id: str) -> list:
        """Load persisted conversation buffer from GitLab, or empty list."""
        try:
            project = self.gl.projects.get(self.base_project)
            learner_path = f"{self.learners_path}/{self._user_folder(user_id)}"
            content = self._read_file(project, f"{learner_path}/conversation.yaml")
            data = yaml.safe_load(content) or {}
            return data.get("messages", [])
        except Exception:
            return []

    # ── Curriculum ────────────────────────────────────────────────────────────

    def save_curriculum_state(self, user_id: str, state: dict):
        try:
            project = self.gl.projects.get(self.base_project)
            path = f"{self.learners_path}/{self._user_folder(user_id)}/curriculum_state.yaml"
            self._write_file(project, path, yaml.dump(state, default_flow_style=False, allow_unicode=True))
        except Exception as e:
            logger.warning(f"Could not save curriculum state for {user_id}: {e}")

    def load_curriculum_state(self, user_id: str) -> dict:
        try:
            project = self.gl.projects.get(self.base_project)
            path = f"{self.learners_path}/{self._user_folder(user_id)}/curriculum_state.yaml"
            return yaml.safe_load(self._read_file(project, path)) or {}
        except Exception:
            return {}

    def clear_curriculum_state(self, user_id: str):
        try:
            project = self.gl.projects.get(self.base_project)
            path = f"{self.learners_path}/{self._user_folder(user_id)}/curriculum_state.yaml"
            project.files.delete(file_path=path, branch=self.branch, commit_message="Clear curriculum state")
        except Exception:
            pass

    def save_curriculum_plan(self, user_id: str, curriculum_id: str, plan: dict):
        try:
            project = self.gl.projects.get(self.base_project)
            path = f"{self.learners_path}/{self._user_folder(user_id)}/curricula/{curriculum_id}/plan.yaml"
            self._write_file(project, path, yaml.dump(plan, default_flow_style=False, allow_unicode=True))
        except Exception as e:
            logger.warning(f"Could not save curriculum plan for {user_id}: {e}")

    def load_curriculum_plan(self, user_id: str, curriculum_id: str) -> dict:
        try:
            project = self.gl.projects.get(self.base_project)
            path = f"{self.learners_path}/{self._user_folder(user_id)}/curricula/{curriculum_id}/plan.yaml"
            return yaml.safe_load(self._read_file(project, path)) or {}
        except Exception:
            return {}

    def get_active_curriculum_id(self, user_id: str) -> str:
        try:
            project = self.gl.projects.get(self.base_project)
            base = f"{self.learners_path}/{self._user_folder(user_id)}/curricula"
            folders = self._list_folders(project, base)
            for curriculum_id in folders:
                try:
                    plan = self.load_curriculum_plan(user_id, curriculum_id)
                    if plan.get("status") == "active":
                        return plan.get("id", "")
                except Exception:
                    continue
        except Exception:
            pass
        return ""

    def _list_folders(self, project, path: str) -> List[str]:
        """List folders (tree items) in a GitLab path"""
        try:
            items = project.repository_tree(path=path, ref=self.branch)
            return [item["name"] for item in items if item["type"] == "tree"]
        except Exception:
            return []

    def _list_files(self, project, path: str) -> List[str]:
        """List files (blob items) in a GitLab path"""
        try:
            items = project.repository_tree(path=path, ref=self.branch)
            return [item["name"] for item in items if item["type"] == "blob"]
        except Exception:
            return []

    def _read_file(self, project, path: str) -> str:
        """Read file content from GitLab"""
        f = project.files.get(file_path=path, ref=self.branch)
        return f.decode().decode("utf-8")

    def _write_file(self, project, path: str, content: str):
        """Write or update file in GitLab"""
        try:
            f = project.files.get(file_path=path, ref=self.branch)
            f.content = content
            f.save(branch=self.branch, commit_message=f"Update {path}")
        except Exception:
            project.files.create({
                "file_path": path,
                "branch": self.branch,
                "content": content,
                "commit_message": f"Create {path}"
            })

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

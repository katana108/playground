"""First-class document operations for Sofico's canonical document store."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from orchestrator.document_manifest import build_topic_document_entry, slugify
from orchestrator.models import CurrentFocus, StudyArtifact, StudyArtifactType
from services.document_resolver_service import DocumentResolverService


def utc_now_iso() -> str:
    """Return a stable UTC timestamp string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DocumentLibraryService:
    """List, inspect, move, and rename canonical learner documents."""

    def __init__(
        self,
        data_service: Any,
        artifact_store: Any,
        document_resolver: DocumentResolverService,
    ):
        self.data_service = data_service
        self.artifact_store = artifact_store
        self.document_resolver = document_resolver

    def list_documents(
        self,
        *,
        user_id: str,
        user_input: str,
        current_focus: CurrentFocus,
        explicit_topic: str = "",
        intent: str = "",
    ) -> Dict[str, Any]:
        """Render a document inventory, optionally scoped to one topic."""
        if intent == "list_topic_folders":
            return self._list_topics_view(user_id)
        if intent == "list_authors":
            return self._list_authors_view(user_id)
        topic = explicit_topic or self._topic_from_context(user_id, user_input, current_focus)
        manifests = (
            self.data_service.get_topic_document_manifests(user_id, topic)
            if topic else
            self.data_service.list_document_manifests(user_id)
        )
        manifests = self._sorted_manifests(manifests)

        if not manifests:
            if topic:
                return {
                    "status": "empty",
                    "message": f"I do not see any saved documents under *{topic}* yet.",
                    "state_delta": {
                        "focus": {
                            "kind": "topic",
                            "topic": topic,
                            "source_message": user_input[:200],
                            "metadata": {"manually_set": True},
                        }
                    },
                }
            return {
                "status": "empty",
                "message": "I do not see any saved documents for you yet.",
            }

        count = len(manifests)
        if topic:
            lines = [f"Here's what I have saved under *{topic}*:"]
        elif count == 1:
            lines = ["You have one saved paper so far:"]
        else:
            lines = [f"Here's your library — {count} papers saved:"]

        for manifest in manifests[:12]:
            lines.append(self._document_bullet(manifest, include_topics=not topic))
        if len(manifests) > 12:
            lines.append(f"- ...and {len(manifests) - 12} more.")

        lines.append(
            "\nSay `show <paper>` for the full profile, `move <paper> to <topic>`, or `rename <paper> to <new name>`."
        )
        result = {
            "status": "ok",
            "message": "\n".join(lines),
        }
        if topic:
            result["state_delta"] = {
                "focus": {
                    "kind": "topic",
                    "topic": topic,
                    "source_message": user_input[:200],
                    "metadata": {"manually_set": True},
                },
                "activity": {
                    "kind": "document_inventory",
                    "summary": f"Listed saved documents under {topic}.",
                    "topic": topic,
                },
            }
        return result

    def show_document(
        self,
        *,
        user_id: str,
        user_input: str,
        current_focus: CurrentFocus,
        target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Render document metadata and readiness for one exact saved document."""
        artifact = self._resolve_artifact(user_id, user_input, current_focus, target=target)
        if not artifact:
            return {
                "status": "missing_document",
                "message": "Tell me which saved paper you want first. For example: `show Ward paper` or `show this paper`.",
            }

        manifest = self._manifest_for_artifact(user_id, artifact)
        title = self._display_title(manifest, artifact)
        original_title = str(manifest.get("title") or "").strip()
        doc_type = str(manifest.get("doc_type") or "").strip() or "document"
        authors = list((((manifest.get("bibliography") or {}).get("authors")) or []))
        year = ((manifest.get("bibliography") or {}).get("year"))
        topics = self._topic_memberships(manifest, artifact)
        question_count = int((((manifest.get("learning") or {}).get("question_count")) or 0) or 0)
        notes_ready = bool((((manifest.get("learning") or {}).get("notes_status")) == "ready"))
        quiz_ready = bool((((manifest.get("learning") or {}).get("quiz_ready"))))
        summary_short = str((((manifest.get("learning") or {}).get("summary_short")) or "")).strip()
        notes = self._document_notes(user_id, manifest, artifact)
        if not summary_short:
            summary_short = self._summary_from_notes(notes)

        header = f"*{title}*"
        if authors:
            author_text = ", ".join(authors[:3])
            if len(authors) > 3:
                author_text += f" +{len(authors) - 3}"
            header += f" — {author_text}"
        if year:
            header += f" ({year})"
        lines = [header]
        if topics:
            lines.append(f"Filed under: {', '.join(topics)}.")
        if summary_short:
            lines.append(f"\n{summary_short}")
        status_parts = []
        if notes_ready:
            status_parts.append("notes ready")
        if quiz_ready:
            status_parts.append(f"{question_count} questions")
        if status_parts:
            lines.append(f"\n_{', '.join(status_parts)}_")
        lines.append(
            "\nSay `show notes on this`, `quiz me on this`, `explain this`, `move this to <topic>`, or `rename this to <new name>`."
        )
        return {
            "status": "ok",
            "message": "\n".join(lines),
            "state_delta": {
                "focus": self._artifact_focus_payload(artifact, user_input),
                "activity": {
                    "kind": "document_profile",
                    "summary": f"Viewed the saved profile for {title}.",
                    "topic": artifact.topic or (topics[0] if topics else ""),
                },
            },
        }

    def move_document(
        self,
        *,
        user_id: str,
        user_input: str,
        current_focus: CurrentFocus,
        target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Move one document from its current topic to another topic."""
        artifact = self._resolve_artifact(user_id, user_input, current_focus, target=target)
        if not artifact:
            return {
                "status": "missing_document",
                "message": "Tell me which saved paper to move first. For example: `move Ward to electromagnetism`.",
            }

        destination_topic = self._parse_destination_topic(user_id, user_input, target)
        if not destination_topic:
            return {
                "status": "missing_destination",
                "message": "Tell me which topic to move it into. For example: `move this paper to consciousness`.",
            }

        manifest = self._manifest_for_artifact(user_id, artifact)
        doc_id = str((artifact.metadata or {}).get("doc_id", "") or manifest.get("doc_id", "") or "").strip()
        doc_name = self._doc_name(manifest, artifact)
        title = self._display_title(manifest, artifact)
        source_topic = str(artifact.topic or self._primary_topic(manifest, artifact)).strip()
        if not doc_name:
            return {
                "status": "error",
                "message": f"I found *{title}*, but I could not determine its saved document path.",
            }
        if destination_topic == source_topic:
            return {
                "status": "noop",
                "message": f"*{title}* is already under *{destination_topic}*.",
                "state_delta": {
                    "focus": self._artifact_focus_payload(artifact, user_input),
                },
            }

        source_content = self._document_source(user_id, manifest, artifact)
        notes = self._document_notes(user_id, manifest, artifact)
        questions = self._document_questions(user_id, manifest, artifact)
        study_document = self._study_document_content(user_id, source_topic, doc_name, notes, questions)

        memberships = self._topic_memberships(manifest, artifact)
        new_memberships = [destination_topic] + [
            item for item in memberships if item and item not in {destination_topic, source_topic}
        ]
        if not new_memberships:
            new_memberships = [destination_topic]

        updated_manifest = dict(manifest)
        updated_manifest["updated_at"] = utc_now_iso()
        updated_manifest.setdefault("classification", {})
        updated_manifest["classification"]["topics"] = new_memberships
        updated_manifest.setdefault("storage", {})
        updated_manifest["storage"]["primary_topic"] = destination_topic
        updated_manifest["storage"]["topic_memberships"] = new_memberships
        updated_manifest["storage"]["legacy_topic_document_path"] = f"topics/{destination_topic}/{doc_name}.md"

        if hasattr(self.data_service, "save_document_bundle"):
            self.data_service.save_document_bundle(
                user_id,
                updated_manifest,
                source_content,
                notes,
                questions,
                merge_manifest=False,
            )

        self.data_service.save_study_document(user_id, destination_topic, doc_name, study_document)
        self._replace_topic_index_document(
            user_id=user_id,
            topic=destination_topic,
            doc_name=doc_name,
            questions=questions,
            tags=self._document_tags(updated_manifest),
            document_entry=build_topic_document_entry(updated_manifest),
        )
        if source_topic:
            self._remove_document_from_topic_index(
                user_id=user_id,
                topic=source_topic,
                doc_id=doc_id,
                doc_name=doc_name,
            )
            if hasattr(self.data_service, "delete_study_document"):
                self.data_service.delete_study_document(user_id, source_topic, doc_name)

        focused_artifact = self._normalize_registry_artifacts(
            user_id=user_id,
            manifest=updated_manifest,
            primary_topic=destination_topic,
            doc_name=doc_name,
        )

        return {
            "status": "moved",
            "message": f"Moved *{title}* from *{source_topic or 'its previous topic'}* to *{destination_topic}*.",
            "state_delta": {
                "focus": self._artifact_focus_payload(focused_artifact or artifact, user_input),
                "activity": {
                    "kind": "document_move",
                    "summary": f"Moved {title} to {destination_topic}.",
                    "topic": destination_topic,
                },
            },
        }

    def delete_topic(
        self,
        *,
        user_id: str,
        topic: str,
    ) -> Dict[str, Any]:
        """Delete a topic folder and remove all its artifacts from the registry."""
        if not topic:
            return {"status": "error", "message": "Tell me which folder to delete — e.g. `delete the consciousness folder`."}

        available = self.data_service.get_available_topics(user_id) or []
        normalized = self._normalize_topic_name(user_id, topic)
        resolved = normalized if normalized in available else (topic if topic in available else "")
        if not resolved:
            return {
                "status": "not_found",
                "message": f"I don't see a saved folder called *{topic}*.",
            }

        # Remove all registry artifacts for this topic
        all_artifacts = self.artifact_store.list_artifacts(user_id)
        remaining = [a for a in all_artifacts if a.topic != resolved]
        removed_count = len(all_artifacts) - len(remaining)
        self.artifact_store.save_artifacts(user_id, remaining)

        # Delete the topic directory and its files via data service
        if hasattr(self.data_service, "delete_topic_folder"):
            self.data_service.delete_topic_folder(user_id, resolved)

        return {
            "status": "deleted",
            "message": f"Deleted folder *{resolved}*{f' and removed {removed_count} saved items' if removed_count else ''}.",
        }

    def rename_document(
        self,
        *,
        user_id: str,
        user_input: str,
        current_focus: CurrentFocus,
        target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Rename the saved display label for one document."""
        artifact = self._resolve_artifact(user_id, user_input, current_focus, target=target)
        if not artifact:
            return {
                "status": "missing_document",
                "message": "Tell me which saved paper to rename first. For example: `rename Ward to EM field paper`.",
            }

        new_title = self._parse_new_title(user_input, target)
        if not new_title:
            return {
                "status": "missing_title",
                "message": "Tell me the new name too. For example: `rename this paper to Ward EM consciousness`.",
            }

        manifest = self._manifest_for_artifact(user_id, artifact)
        current_title = self._display_title(manifest, artifact)
        if new_title == current_title:
            return {
                "status": "noop",
                "message": f"It is already saved as *{new_title}*.",
                "state_delta": {
                    "focus": self._artifact_focus_payload(artifact, user_input),
                },
            }

        doc_name = self._doc_name(manifest, artifact)
        source_content = self._document_source(user_id, manifest, artifact)
        notes = self._document_notes(user_id, manifest, artifact)
        questions = self._document_questions(user_id, manifest, artifact)

        updated_manifest = dict(manifest)
        updated_manifest["updated_at"] = utc_now_iso()
        updated_manifest["display_title"] = new_title
        updated_manifest["slug"] = slugify(new_title, fallback=updated_manifest.get("slug", "document") or "document")
        updated_manifest.setdefault("source", {})
        updated_manifest["source"]["source_label"] = new_title

        if hasattr(self.data_service, "save_document_bundle"):
            self.data_service.save_document_bundle(
                user_id,
                updated_manifest,
                source_content,
                notes,
                questions,
                merge_manifest=False,
            )

        for topic in self._topic_memberships(updated_manifest, artifact):
            self._replace_topic_index_document(
                user_id=user_id,
                topic=topic,
                doc_name=doc_name,
                questions=None,
                tags=self._document_tags(updated_manifest),
                document_entry=build_topic_document_entry(updated_manifest),
            )

        focused_artifact = self._normalize_registry_artifacts(
            user_id=user_id,
            manifest=updated_manifest,
            primary_topic=self._primary_topic(updated_manifest, artifact),
            doc_name=doc_name,
        )

        return {
            "status": "renamed",
            "message": f"Renamed the saved label from *{current_title}* to *{new_title}*. The underlying document stayed the same.",
            "state_delta": {
                "focus": self._artifact_focus_payload(focused_artifact or artifact, user_input),
                "activity": {
                    "kind": "document_rename",
                    "summary": f"Renamed {current_title} to {new_title}.",
                    "topic": (focused_artifact or artifact).topic or self._primary_topic(updated_manifest, artifact),
                },
            },
        }

    def _resolve_artifact(
        self,
        user_id: str,
        user_input: str,
        current_focus: CurrentFocus,
        *,
        target: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """Resolve one artifact from a message, target hints, or current focus.

        Resolution order:
        1. LLM's document_hint — the turn interpreter already identified the paper.
        2. Raw keyword match against user_input — fallback for when no hint was set.
        3. Current focus — last resort.

        The hint must come first because user messages often contain destination
        topic names, paper titles listed for context, and other words that cause
        raw keyword matching to select the wrong paper.
        """
        hint = ""
        if target:
            hint = str(
                (target.get("document_hint") or target.get("artifact_hint") or "")
            ).strip()
            if hint:
                hinted = self.document_resolver.select_document_artifact(
                    self.document_resolver.matching_artifacts(user_id, hint)
                )
                if hinted:
                    return hinted

        # Only fall through to raw user_input matching / focus if no explicit hint
        # was provided — when a hint exists but scores zero, return None so the
        # caller can surface a "couldn't find that paper" error rather than silently
        # operating on whatever happens to be in focus.
        if hint:
            return None

        selected = self.document_resolver.select_document_artifact(
            self.document_resolver.matching_artifacts(user_id, user_input)
        )
        if selected:
            return selected

        return self.document_resolver.focused_artifact(user_id, current_focus)

    def _list_topics_view(self, user_id: str) -> Dict[str, Any]:
        """Render just the topic folders with paper and question counts."""
        topics = [t for t in (self.data_service.get_available_topics(user_id) or []) if len(t) <= 60]
        if not topics:
            return {"status": "empty", "message": "You don't have any saved topics yet."}
        lines = [f"Your topics ({len(topics)}):"]
        for topic in sorted(topics):
            index_data = self.data_service.get_topic_index(user_id, topic) or {}
            q_count = len(index_data.get("questions", []) or [])
            docs = index_data.get("documents", []) or []
            doc_count = len(docs)
            paper_text = f"{doc_count} paper{'s' if doc_count != 1 else ''}"
            q_text = f"{q_count} questions" if q_count else "no questions yet"
            lines.append(f"- *{topic}* — {paper_text}, {q_text}")
        lines.append('\nSay "what papers are in [topic]?" or "quiz me on [topic]".')
        return {"status": "ok", "message": "\n".join(lines)}

    def _list_authors_view(self, user_id: str) -> Dict[str, Any]:
        """Render unique authors across all saved documents."""
        manifests = self.data_service.list_document_manifests(user_id) or []
        author_papers: Dict[str, List[str]] = {}
        for manifest in manifests:
            authors = list(((manifest.get("bibliography") or {}).get("authors") or []))
            title = str(manifest.get("display_title") or manifest.get("title") or "untitled").strip()
            for author in authors:
                author_papers.setdefault(author, []).append(title)
        if not author_papers:
            return {"status": "empty", "message": "No authors found in your saved library."}
        lines = [f"Authors in your library ({len(author_papers)}):"]
        for author in sorted(author_papers):
            papers = author_papers[author]
            paper_list = ", ".join(f"*{p}*" for p in papers[:3])
            if len(papers) > 3:
                paper_list += f" +{len(papers) - 3} more"
            lines.append(f"- {author} — {paper_list}")
        lines.append('\nSay "show me papers by [author]" to filter.')
        return {"status": "ok", "message": "\n".join(lines)}

    def _topic_from_context(self, user_id: str, user_input: str, current_focus: CurrentFocus) -> str:
        """Resolve the topic scope from explicit words, then current focus."""
        available_topics = self.data_service.get_available_topics(user_id) or []
        explicit = self.document_resolver.extract_topic_reference(user_input, available_topics)
        if explicit:
            return explicit
        lowered = user_input.lower()
        if any(token in lowered for token in ("this folder", "this topic", "these papers", "my papers here")):
            return current_focus.topic or ""
        return ""

    def _manifest_for_artifact(self, user_id: str, artifact: Any) -> Dict[str, Any]:
        """Load the canonical manifest linked to an artifact."""
        doc_id = str((artifact.metadata or {}).get("doc_id", "") or "").strip()
        if doc_id and hasattr(self.data_service, "get_document_manifest"):
            return self.data_service.get_document_manifest(user_id, doc_id) or {}
        return {}

    def _document_source(self, user_id: str, manifest: Dict[str, Any], artifact: Any) -> str:
        """Load canonical source text, falling back to legacy content."""
        doc_id = str(manifest.get("doc_id", "") or (artifact.metadata or {}).get("doc_id", "") or "").strip()
        if doc_id and hasattr(self.data_service, "get_document_source"):
            content = self.data_service.get_document_source(user_id, doc_id) or ""
            if content:
                return content
        topic = str(artifact.topic or self._primary_topic(manifest, artifact)).strip()
        doc_name = self._doc_name(manifest, artifact)
        if topic and doc_name and hasattr(self.data_service, "get_study_document_content"):
            return self.data_service.get_study_document_content(user_id, topic, doc_name) or ""
        return ""

    def _document_notes(self, user_id: str, manifest: Dict[str, Any], artifact: Any) -> str:
        """Load canonical notes, falling back to legacy topic notes."""
        doc_id = str(manifest.get("doc_id", "") or (artifact.metadata or {}).get("doc_id", "") or "").strip()
        if doc_id and hasattr(self.data_service, "get_document_notes"):
            notes = self.data_service.get_document_notes(user_id, doc_id) or ""
            if notes:
                return notes
        topic = str(artifact.topic or self._primary_topic(manifest, artifact)).strip()
        doc_name = self._doc_name(manifest, artifact)
        if topic and doc_name and hasattr(self.data_service, "get_study_document_notes"):
            return self.data_service.get_study_document_notes(user_id, topic, doc_name) or ""
        return ""

    def _document_questions(self, user_id: str, manifest: Dict[str, Any], artifact: Any) -> List[Dict[str, Any]]:
        """Load canonical questions, falling back to topic-index questions."""
        doc_id = str(manifest.get("doc_id", "") or (artifact.metadata or {}).get("doc_id", "") or "").strip()
        if doc_id and hasattr(self.data_service, "get_document_questions"):
            questions = self.data_service.get_document_questions(user_id, doc_id) or []
            if questions:
                return list(questions)

        topic = str(artifact.topic or self._primary_topic(manifest, artifact)).strip()
        doc_name = self._doc_name(manifest, artifact)
        if not topic or not doc_name:
            return []
        index_data = self.data_service.get_topic_index(user_id, topic) or {}
        prefixes = {f"{doc_name}.md#", f"{Path(doc_name).stem}.md#"}
        return [
            question
            for question in index_data.get("questions", []) or []
            if any(str(question.get("id", "") or "").startswith(prefix) for prefix in prefixes)
        ]

    def _study_document_content(
        self,
        user_id: str,
        topic: str,
        doc_name: str,
        notes: str,
        questions: List[Dict[str, Any]],
    ) -> str:
        """Load or reconstruct the compatibility topic document."""
        if topic and doc_name and hasattr(self.data_service, "get_study_document_content"):
            content = self.data_service.get_study_document_content(user_id, topic, doc_name) or ""
            if content:
                return content
        return self._build_study_document(notes, questions)

    def _build_study_document(self, notes: str, questions: List[Dict[str, Any]]) -> str:
        """Reconstruct the markdown compatibility document."""
        notes_block = (notes or "").strip()
        question_block = self._render_question_section(questions).strip()
        if not question_block:
            return notes_block
        if not notes_block:
            return question_block
        return f"{notes_block}\n\n---\n\n{question_block}"

    def _render_question_section(self, questions: List[Dict[str, Any]]) -> str:
        """Render stored questions back into the markdown review format."""
        ordered_categories = ["Recall", "Explain", "Apply", "Connect"]
        by_category: Dict[str, List[Dict[str, Any]]] = {name: [] for name in ordered_categories}
        for question in questions:
            category = str(question.get("category") or question.get("type") or "").strip().title()
            if category not in by_category:
                by_category.setdefault(category, [])
            by_category[category].append(question)

        lines = ["## Anki Questions", ""]
        number = 1
        for category in ordered_categories:
            items = by_category.get(category, [])
            if not items:
                continue
            lines.append(f"### {category}")
            lines.append("")
            for question in items:
                text = str(question.get("text") or "").strip()
                answer = str(question.get("answer") or "").strip()
                if not text or not answer:
                    continue
                lines.append(f"**Q{number}:** {text}")
                lines.append(f"**A{number}:** {answer}")
                lines.append("")
                number += 1
        return "\n".join(lines).rstrip()

    def _replace_topic_index_document(
        self,
        *,
        user_id: str,
        topic: str,
        doc_name: str,
        document_entry: Dict[str, Any],
        tags: List[str],
        questions: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Replace one document entry, and optionally its questions, inside a topic index."""
        index_data = self.data_service.get_topic_index(user_id, topic) or {}
        index_data.setdefault("topic", topic)
        index_data.setdefault("questions", [])
        index_data.setdefault("documents", [])

        prefixes = {f"{doc_name}.md#", f"{Path(doc_name).stem}.md#"}
        if questions is not None:
            retained_questions = [
                question
                for question in index_data.get("questions", []) or []
                if not any(str(question.get("id", "") or "").startswith(prefix) for prefix in prefixes)
            ]
            prepared_questions = []
            for question in questions:
                payload = dict(question)
                payload["tags"] = list(tags)
                prepared_questions.append(payload)
            retained_questions.extend(prepared_questions)
            index_data["questions"] = retained_questions

        wanted_doc_id = str(document_entry.get("doc_id", "") or "").strip()
        documents = []
        for existing in index_data.get("documents", []) or []:
            if not isinstance(existing, dict):
                continue
            if wanted_doc_id and str(existing.get("doc_id", "") or "").strip() == wanted_doc_id:
                continue
            documents.append(existing)
        documents.append(document_entry)
        index_data["documents"] = documents
        index_data["last_updated"] = date.today().isoformat()
        self.data_service.update_topic_index(user_id, topic, index_data)

    def _remove_document_from_topic_index(
        self,
        *,
        user_id: str,
        topic: str,
        doc_id: str,
        doc_name: str,
    ) -> None:
        """Remove one document's entry and questions from a topic index."""
        index_data = self.data_service.get_topic_index(user_id, topic) or {}
        index_data.setdefault("questions", [])
        index_data.setdefault("documents", [])
        prefixes = {f"{doc_name}.md#", f"{Path(doc_name).stem}.md#"}
        index_data["questions"] = [
            question
            for question in index_data.get("questions", []) or []
            if not any(str(question.get("id", "") or "").startswith(prefix) for prefix in prefixes)
        ]
        wanted_doc_id = str(doc_id or "").strip()
        index_data["documents"] = [
            item
            for item in index_data.get("documents", []) or []
            if not (isinstance(item, dict) and wanted_doc_id and str(item.get("doc_id", "") or "").strip() == wanted_doc_id)
        ]
        index_data["last_updated"] = date.today().isoformat()
        self.data_service.update_topic_index(user_id, topic, index_data)

    def _normalize_registry_artifacts(
        self,
        *,
        user_id: str,
        manifest: Dict[str, Any],
        primary_topic: str,
        doc_name: str,
    ) -> Optional[StudyArtifact]:
        """Keep one uploaded_source, one notes, and one question_set artifact per document."""
        doc_id = str(manifest.get("doc_id", "") or "").strip()
        if not doc_id:
            return None

        source_label = str(((manifest.get("source") or {}).get("source_label")) or manifest.get("display_title") or manifest.get("title") or doc_name).strip()
        doc_type = str(manifest.get("doc_type", "") or "").strip()
        authors = list((((manifest.get("bibliography") or {}).get("authors")) or []))
        year = ((manifest.get("bibliography") or {}).get("year"))
        summary_short = str((((manifest.get("learning") or {}).get("summary_short")) or "")).strip()
        question_count = int((((manifest.get("learning") or {}).get("question_count")) or 0) or 0)
        tags = self._document_tags(manifest)
        source_path = f"{primary_topic}/{doc_name}.md"

        artifacts = self.artifact_store.list_artifacts(user_id)
        matching = [
            artifact
            for artifact in artifacts
            if str((artifact.metadata or {}).get("doc_id", "") or "").strip() == doc_id
        ]
        kept_by_type: Dict[StudyArtifactType, StudyArtifact] = {}
        others: List[StudyArtifact] = []
        for artifact in artifacts:
            if artifact in matching:
                kept_by_type.setdefault(artifact.artifact_type, artifact)
            else:
                others.append(artifact)

        uploaded = kept_by_type.get(StudyArtifactType.UPLOADED_SOURCE) or StudyArtifact(
            artifact_id=uuid4().hex,
            artifact_type=StudyArtifactType.UPLOADED_SOURCE,
            title=source_label,
            user_id=user_id,
            created_at=utc_now_iso(),
        )
        uploaded.title = source_label
        uploaded.topic = primary_topic
        uploaded.source_path = source_path
        uploaded.metadata = {
            "source_label": source_label,
            "source_kind": "ingested_material",
            "doc_name": doc_name,
            "doc_id": doc_id,
            "doc_type": doc_type,
            "authors": authors,
            "year": year,
        }

        notes_artifact = kept_by_type.get(StudyArtifactType.NOTES) or StudyArtifact(
            artifact_id=uuid4().hex,
            artifact_type=StudyArtifactType.NOTES,
            title=source_label,
            user_id=user_id,
            created_at=utc_now_iso(),
        )
        notes_artifact.title = source_label
        notes_artifact.topic = primary_topic
        notes_artifact.source_path = source_path
        notes_artifact.metadata = {
            "tags": tags,
            "question_count": question_count,
            "doc_id": doc_id,
            "summary_short": summary_short,
            "authors": authors,
            "year": year,
            "doc_type": doc_type,
        }

        question_set = kept_by_type.get(StudyArtifactType.QUESTION_SET) or StudyArtifact(
            artifact_id=uuid4().hex,
            artifact_type=StudyArtifactType.QUESTION_SET,
            title=f"{source_label} questions",
            user_id=user_id,
            created_at=utc_now_iso(),
        )
        question_set.title = f"{source_label} questions"
        question_set.topic = primary_topic
        question_set.source_path = source_path
        question_set.source_artifact_id = notes_artifact.artifact_id or uploaded.artifact_id
        question_set.metadata = {
            "question_count": question_count,
            "tags": tags,
            "doc_id": doc_id,
            "doc_type": doc_type,
        }

        normalized = others + [uploaded, notes_artifact, question_set]
        self.artifact_store.save_artifacts(user_id, normalized)
        return uploaded

    def _parse_destination_topic(
        self,
        user_id: str,
        user_input: str,
        target: Optional[Dict[str, Any]],
    ) -> str:
        """Extract a destination topic from interpreter hints or raw text."""
        raw = ""
        if target:
            raw = str(
                target.get("destination_topic")
                or target.get("topic")
                or ""
            ).strip()
        if not raw:
            lowered = user_input.lower()
            for marker in (" to ", " into ", " under "):
                if marker in lowered:
                    idx = lowered.rfind(marker)
                    raw = user_input[idx + len(marker):].strip(" .")
                    break
        if not raw:
            return ""
        return self._normalize_topic_name(user_id, raw)

    def _parse_new_title(self, user_input: str, target: Optional[Dict[str, Any]]) -> str:
        """Extract the requested new display title from target hints or raw text."""
        if target:
            hinted = str(target.get("new_title") or "").strip()
            if hinted:
                return hinted

        lowered = user_input.lower()
        for marker in (" to ", " as "):
            if marker in lowered:
                idx = lowered.rfind(marker)
                candidate = user_input[idx + len(marker):].strip(" .")
                if candidate:
                    return candidate
        if lowered.startswith("call this paper "):
            return user_input[len("call this paper "):].strip(" .")
        if lowered.startswith("name this paper "):
            return user_input[len("name this paper "):].strip(" .")
        return ""

    def _normalize_topic_name(self, user_id: str, raw: str) -> str:
        """Prefer an existing topic match; otherwise slugify a new topic name.

        Matching order:
        1. Exact match (case-insensitive, hyphens/underscores as spaces)
        2. Existing topic starts with the user's word(s) — "philosophy" → "philosophy-of-consciousness"
        3. Slugify the raw text as a new topic name
        """
        clean = str(raw or "").strip()
        if not clean:
            return ""
        available = self.data_service.get_available_topics(user_id) or []
        lowered = clean.lower()
        normalized = clean.lower().replace("_", " ").replace("-", " ")
        for topic in available:
            topic_norm = topic.lower().replace("_", " ").replace("-", " ")
            if topic.lower() == lowered or topic_norm == normalized:
                return topic
        for topic in available:
            topic_norm = topic.lower().replace("_", " ").replace("-", " ")
            if topic_norm.startswith(normalized):
                return topic
        return slugify(clean, fallback="topic")

    def _artifact_focus_payload(self, artifact: Any, source_message: str) -> Dict[str, Any]:
        """Return a focus payload that SessionController can persist."""
        topic = str(artifact.topic or "").strip()
        doc_name = self.document_resolver.artifact_doc_name(artifact)
        return {
            "kind": "artifact",
            "artifact_id": artifact.artifact_id,
            "topic": topic,
            "source_message": source_message[:200],
            "updated_at": utc_now_iso(),
            "metadata": {
                "document_title": self.document_resolver.artifact_title(artifact),
                "doc_name": doc_name,
                "source_path": artifact.source_path or f"{topic}/{doc_name}.md",
                "matched_document_answer": False,
            },
        }

    def _document_bullet(self, manifest: Dict[str, Any], *, include_topics: bool) -> str:
        """Render one compact document inventory line."""
        title = str(manifest.get("display_title") or manifest.get("title") or manifest.get("slug") or "untitled").strip()
        authors = list((((manifest.get("bibliography") or {}).get("authors")) or []))
        year = ((manifest.get("bibliography") or {}).get("year"))
        question_count = int((((manifest.get("learning") or {}).get("question_count")) or 0) or 0)
        notes_ready = bool((((manifest.get("learning") or {}).get("notes_status")) == "ready"))
        parts = [f"- {title}"]
        if authors:
            author_text = ", ".join(authors[:2])
            if len(authors) > 2:
                author_text += f" +{len(authors) - 2}"
            parts.append(f"by {author_text}")
        if year:
            parts.append(str(year))
        parts.append(f"{question_count} questions")
        parts.append("notes ready" if notes_ready else "notes missing")
        if include_topics:
            topics = [t for t in self._topic_memberships(manifest, None) if len(t) <= 60]
            if topics:
                parts.append(f"topics: {', '.join(topics[:3])}")
        return " — ".join(parts) + "."

    def _sorted_manifests(self, manifests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort saved documents with the most recently updated first."""
        return sorted(
            manifests,
            key=lambda item: (
                str(item.get("updated_at") or ""),
                str(item.get("display_title") or item.get("title") or ""),
            ),
            reverse=True,
        )

    def _summary_from_notes(self, notes: str) -> str:
        """Fall back to the first paragraph of notes when no short summary exists."""
        clean = (notes or "").strip()
        if not clean:
            return ""
        first_block = clean.split("\n\n", 1)[0].strip()
        return first_block[:280] + ("..." if len(first_block) > 280 else "")

    def _primary_topic(self, manifest: Dict[str, Any], artifact: Any) -> str:
        """Return the best current primary topic for a document."""
        storage = manifest.get("storage") or {}
        return str(storage.get("primary_topic") or getattr(artifact, "topic", "") or "").strip()

    def _doc_name(self, manifest: Dict[str, Any], artifact: Any) -> str:
        """Return the legacy topic-doc stem used for compatibility files."""
        storage = manifest.get("storage") or {}
        legacy_path = str(storage.get("legacy_topic_document_path") or getattr(artifact, "source_path", "") or "").strip()
        if not legacy_path:
            return ""
        name = Path(legacy_path).name
        return name[:-3] if name.endswith(".md") else name

    def _display_title(self, manifest: Dict[str, Any], artifact: Any) -> str:
        """Return the most useful human-readable title."""
        return (
            str(manifest.get("display_title") or manifest.get("title") or "").strip()
            or self.document_resolver.artifact_title(artifact)
        )

    def _topic_memberships(self, manifest: Dict[str, Any], artifact: Any = None) -> List[str]:
        """Return the deduplicated topic memberships for a document."""
        memberships: List[str] = []
        memberships.extend((((manifest.get("storage") or {}).get("topic_memberships")) or []))
        memberships.extend((((manifest.get("classification") or {}).get("topics")) or []))
        primary = str(((manifest.get("storage") or {}).get("primary_topic")) or "").strip()
        if primary:
            memberships.insert(0, primary)
        if artifact and getattr(artifact, "topic", ""):
            memberships.insert(0, artifact.topic)
        ordered: List[str] = []
        seen = set()
        for item in memberships:
            clean = str(item or "").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            ordered.append(clean)
        return ordered

    def _document_tags(self, manifest: Dict[str, Any]) -> List[str]:
        """Return the current keyword/tag list from one manifest."""
        return list((((manifest.get("knowledge") or {}).get("keywords")) or []))

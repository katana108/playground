"""Read-only artifact/document display helpers for Sofico."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from orchestrator.artifact_store import ArtifactStore
from orchestrator.models import CurrentFocus
from services.document_resolver_service import DocumentResolverService


@dataclass
class ArtifactViewOutcome:
    """Rendered artifact response plus the state updates it implies."""

    message: str
    focus_artifact: Any = None
    focus_topic: str = ""
    clear_learning_modes: bool = False
    activity_kind: str = ""
    activity_summary: str = ""
    activity_topic: str = ""


class ArtifactViewService:
    """Render saved notes, questions, and artifact inventory."""

    def __init__(
        self,
        data_service: Any,
        artifact_store: ArtifactStore,
        document_resolver: DocumentResolverService,
    ):
        self.data_service = data_service
        self.artifact_store = artifact_store
        self.document_resolver = document_resolver

    def show_artifacts(
        self,
        *,
        user_id: str,
        user_input: str,
        current_focus: CurrentFocus,
        explicit_topic: Optional[str],
        resolved_topic: Optional[str],
        references_current_material: bool,
        inventory_request: bool,
    ) -> ArtifactViewOutcome:
        """Render the best artifact/material response for a learner turn."""
        matching_artifacts = self.document_resolver.matching_artifacts(user_id, user_input)
        exact_notes_request = self.is_exact_notes_request(user_input)
        exact_question_request = self.is_exact_question_request(user_input)
        exact_artifact = self.document_resolver.resolve_requested_artifact(
            user_id,
            user_input,
            current_focus,
            explicit_topic=explicit_topic,
            exact_notes_request=exact_notes_request,
            exact_question_request=exact_question_request,
            references_current_material=references_current_material,
        )

        if exact_notes_request and exact_artifact:
            return self._show_exact_artifact_notes(user_id, exact_artifact)

        if exact_notes_request and not exact_artifact and not matching_artifacts:
            named = self._extract_named_document(user_input)
            if named:
                return ArtifactViewOutcome(
                    message=f"Sofico: I don't have a document called *{named}* saved. Here are the topics I have instead:"
                    + self._topic_list_suffix(user_id),
                )

        if exact_question_request and exact_artifact:
            return self._show_exact_artifact_questions(user_id, exact_artifact)

        topic = explicit_topic
        if not topic:
            if matching_artifacts:
                return self._show_matching_artifacts(matching_artifacts)
            topic = resolved_topic
        if not topic:
            return self._show_recent_artifacts(user_id, user_input)

        return self._show_topic_inventory(user_id, topic)

    def is_exact_notes_request(self, user_input: str) -> bool:
        """Return True when the learner wants saved notes for one document."""
        lowered = user_input.lower().strip()
        direct_phrases = (
            "show notes",
            "show me notes",
            "give me notes",
            "give me the notes",
            "notes on",
            "notes for",
            "summary of",
            "give me a summary",
            "show summary",
            "show me the summary",
            "give me summary",
        )
        return any(phrase in lowered for phrase in direct_phrases)

    def is_exact_question_request(self, user_input: str) -> bool:
        """Return True when the learner wants the saved questions for one document."""
        lowered = user_input.lower().strip()
        direct_phrases = (
            "what questions did you make",
            "show questions",
            "show me questions",
            "show quiz questions",
            "show the questions",
            "what cards did you make",
            "show cards",
            "show me cards",
        )
        return any(phrase in lowered for phrase in direct_phrases)

    def _show_topic_inventory(self, user_id: str, topic: str) -> ArtifactViewOutcome:
        """Render the topic-scoped saved-material overview."""
        notes = self.data_service.get_topic_notes(user_id, topic)
        index_data = self.data_service.get_topic_index(user_id, topic)
        questions = index_data.get("questions", []) if isinstance(index_data, dict) else []
        artifacts = self.artifact_store.find_by_topic(user_id, topic)

        if not notes and not questions and not artifacts:
            return ArtifactViewOutcome(
                message=f"Sofico: Looks like I haven't saved anything under *{topic}* yet — try uploading a document first!"
            )

        lines = [f"Sofico: Here's what I have for *{topic}*:"]
        if artifacts:
            artifact_counts: Dict[str, int] = {}
            for artifact in artifacts:
                artifact_counts[artifact.artifact_type.value] = artifact_counts.get(artifact.artifact_type.value, 0) + 1
            counts_text = ", ".join(
                f"{count} {kind.replace('_', ' ')}"
                for kind, count in sorted(artifact_counts.items())
            )
            lines.append(f"- Artifacts: {counts_text}.")
            document_lines = self._document_lines_for_artifacts(artifacts)
            if document_lines:
                lines.append("- Documents:")
                lines.extend(document_lines[:8])

        if notes:
            lines.append("- Notes: yep, here are the first key pieces:")
            lines.extend(self._note_preview_lines(notes))
        else:
            lines.append("- Notes: nothing saved here yet.")

        if questions:
            categories: Dict[str, int] = {}
            for question in questions:
                category = question.get("category", "uncategorized")
                categories[category] = categories.get(category, 0) + 1
            category_text = ", ".join(f"{category}: {count}" for category, count in sorted(categories.items()))
            lines.append(f"- Questions: {len(questions)} total ({category_text}).")
            for question in questions[:3]:
                text = (question.get("text") or "").strip()
                if text:
                    lines.append(f"  - {text}")
        else:
            lines.append("- Questions: no review questions yet — upload a doc and I'll generate some!")

        lines.append("\nYou can say `explain it` or `quiz me` and I’ll use this topic.")
        return ArtifactViewOutcome(
            message="\n".join(lines),
            focus_topic=topic,
            activity_kind="artifact_review",
            activity_summary=f"Reviewed saved notes and questions for {topic}.",
            activity_topic=topic,
        )

    def _show_matching_artifacts(self, artifacts: List[Any]) -> ArtifactViewOutcome:
        """Render a grouped list of matching saved documents."""
        selected = self.document_resolver.select_document_artifact(artifacts)
        unique_documents = {
            (
                str((artifact.metadata or {}).get("doc_id", "") or "").strip(),
                str(artifact.source_path or (artifact.metadata or {}).get("doc_name", "") or "").strip(),
            )
            for artifact in artifacts
            if artifact.artifact_type.value in {"uploaded_source", "notes"}
        }

        grouped: Dict[str, List[Any]] = {}
        for artifact in artifacts:
            grouped.setdefault(artifact.topic or "uncategorized", []).append(artifact)

        lines = ["Sofico: I found saved material matching that:"]
        for topic, topic_artifacts in sorted(grouped.items()):
            lines.append(f"- Under *{topic}*:")
            lines.extend(self._document_lines_for_artifacts(topic_artifacts) or [
                f"  - {artifact.title or artifact.source_path or artifact.artifact_type.value}"
                for artifact in topic_artifacts[:5]
            ])
        lines.append("\nYou can ask me to `explain this paper`, `show notes on <topic>`, or `quiz me on <topic>`.")
        return ArtifactViewOutcome(
            message="\n".join(lines),
            focus_artifact=selected if selected and len(unique_documents) == 1 else None,
        )

    def _show_exact_artifact_notes(self, user_id: str, artifact: Any) -> ArtifactViewOutcome:
        """Render canonical notes for one exact document."""
        notes = self._load_artifact_notes(user_id, artifact)
        title = self.document_resolver.artifact_title(artifact)
        if not notes:
            return ArtifactViewOutcome(
                message=f"Sofico: I have *{title}* saved, but no notes for it yet — want me to explain it instead?"
            )

        rendered_notes = notes.strip()
        if len(rendered_notes) > 20000:
            rendered_notes = rendered_notes[:20000].rstrip() + "\n\n[Notes continue — say *more notes* to see the rest.]"

        return ArtifactViewOutcome(
            message=(
                f"Sofico: Here are my notes on *{title}*:\n\n"
                f"{rendered_notes}\n\n"
                "You can say `explain this paper`, `quiz me on this`, or `what questions did you make for this paper`."
            ),
            focus_artifact=artifact,
            clear_learning_modes=True,
        )

    def _show_exact_artifact_questions(self, user_id: str, artifact: Any) -> ArtifactViewOutcome:
        """Render saved questions for one exact document."""
        questions = self._load_artifact_questions(user_id, artifact)
        title = self.document_resolver.artifact_title(artifact)
        if not questions:
            return ArtifactViewOutcome(
                message=f"Sofico: I have *{title}* saved, but no review questions for it yet — say *quiz me on {title}* and I'll generate some!"
            )

        categories: Dict[str, int] = {}
        for question in questions:
            category = str(question.get("category") or question.get("type") or "uncategorized")
            categories[category] = categories.get(category, 0) + 1
        category_text = ", ".join(f"{category}: {count}" for category, count in sorted(categories.items()))

        lines = [f"Sofico: Here are the saved questions for *{title}*:"]
        lines.append(f"- {len(questions)} total ({category_text}).")
        for question in questions[:8]:
            text = str(question.get("text") or "").strip()
            if text:
                lines.append(f"  - {text}")
        if len(questions) > 8:
            lines.append(f"  - ...and {len(questions) - 8} more.")
        lines.append("\nYou can say `quiz me on this` and I’ll use this document.")
        return ArtifactViewOutcome(
            message="\n".join(lines),
            focus_artifact=artifact,
            clear_learning_modes=True,
        )

    def _show_recent_artifacts(self, user_id: str, user_input: str = "") -> ArtifactViewOutcome:
        """Render the broad saved-material inventory view."""
        artifacts = self.artifact_store.list_artifacts(user_id)
        topics = self.data_service.get_available_topics(user_id)

        if not artifacts and not topics:
            return ArtifactViewOutcome(
                message="Sofico: Nothing saved yet — upload a document or paste some text and I'll turn it into study materials!"
            )

        lines = ["Sofico: Here is what I can see in your study workspace:"]
        if topics:
            requested_label = (
                self._requested_material_label(user_input, topics)
                if self._looks_like_specific_material_lookup(user_input)
                else ""
            )
            if requested_label:
                lines.append(f"- I do not see an exact saved topic matching `{requested_label}`.")
            lines.append("- Saved topics:")
            visible_topics = topics[:12]
            for topic in visible_topics:
                index_data = self.data_service.get_topic_index(user_id, topic)
                questions = index_data.get("questions", []) if isinstance(index_data, dict) else []
                notes = self.data_service.get_topic_notes(user_id, topic)
                notes_text = "notes" if notes else "no readable notes"
                question_text = f"{len(questions)} questions" if questions else "no indexed questions"
                lines.append(f"  - {topic}: {notes_text}, {question_text}")
            if len(topics) > len(visible_topics):
                lines.append(f"  - ...and {len(topics) - len(visible_topics)} more topics.")

        if artifacts:
            for artifact in artifacts[-6:]:
                kind = artifact.artifact_type.value.replace("_", " ")
                title = artifact.title or artifact.topic or "untitled"
                topic = f" under *{artifact.topic}*" if artifact.topic else ""
                lines.append(f"- {kind}: {title}{topic}")

        lines.append("\nAsk `show notes on <topic>` or `what questions did you make for <topic>` for details.")
        return ArtifactViewOutcome(message="\n".join(lines))

    def _extract_named_document(self, user_input: str) -> str:
        """Pull the document name from 'show me notes for X' / 'notes on X' patterns."""
        import re
        lowered = user_input.lower().strip()
        for phrase in ("notes for", "notes on", "show me notes for", "show me notes on",
                       "show notes for", "show notes on", "give me notes for", "give me notes on",
                       "summary of", "give me a summary of", "show summary of"):
            if phrase in lowered:
                after = user_input[lowered.index(phrase) + len(phrase):].strip()
                if after:
                    return after
        return ""

    def _topic_list_suffix(self, user_id: str) -> str:
        """Return a short newline-prefixed list of saved topics for 'not found' messages."""
        try:
            topics = [
                t for t in (self.data_service.get_available_topics(user_id) or [])
                if len(t) <= 60
            ]
            if not topics:
                return ""
            return "\n\n*Your saved topics:* " + ", ".join(topics[:10])
        except Exception:
            return ""

    def _resolve_doc_id(self, user_id: str, artifact: Any) -> str:
        """Return doc_id for an artifact, with fallback for legacy artifacts that lack it in metadata."""
        doc_id = str((artifact.metadata or {}).get("doc_id", "") or "").strip()
        if doc_id:
            return doc_id
        source_path = str(artifact.source_path or "").strip()
        if source_path:
            for companion in self.artifact_store.list_artifacts(user_id):
                if companion.artifact_id == artifact.artifact_id:
                    continue
                if str(companion.source_path or "").strip() != source_path:
                    continue
                candidate = str((companion.metadata or {}).get("doc_id", "") or "").strip()
                if candidate:
                    return candidate
        doc_name = self.document_resolver.artifact_doc_name(artifact)
        if doc_name and hasattr(self.data_service, "list_document_manifests"):
            source_path_norm = str(artifact.source_path or "").strip()
            for manifest in self.data_service.list_document_manifests(user_id):
                storage = manifest.get("storage") or {}
                manifest_legacy = str(storage.get("legacy_topic_document_path", "") or "").strip()
                manifest_slug = str(manifest.get("slug", "") or "").strip()
                legacy_doc_name = Path(manifest_legacy).stem if manifest_legacy else ""
                if (
                    (source_path_norm and manifest_legacy == f"topics/{source_path_norm}")
                    or (legacy_doc_name and legacy_doc_name.lower() == doc_name.lower())
                    or (manifest_slug and manifest_slug.lower() == doc_name.lower())
                ):
                    found = str(manifest.get("doc_id", "") or "").strip()
                    if found:
                        return found
        return ""

    def _load_artifact_notes(self, user_id: str, artifact: Any) -> str:
        """Load canonical or legacy notes for one document artifact."""
        doc_id = self._resolve_doc_id(user_id, artifact)
        if doc_id and hasattr(self.data_service, "get_document_notes"):
            notes = self.data_service.get_document_notes(user_id, doc_id) or ""
            if notes:
                return notes

        topic = (artifact.topic or "").strip()
        doc_name = self.document_resolver.artifact_doc_name(artifact)
        if not topic or not doc_name:
            return ""

        if hasattr(self.data_service, "get_study_document_notes"):
            notes = self.data_service.get_study_document_notes(user_id, topic, doc_name) or ""
            if notes:
                return notes

        topic_notes = self.data_service.get_topic_notes(user_id, topic)
        if not topic_notes:
            return ""
        marker = f"### {Path(doc_name).stem}"
        if marker not in topic_notes:
            return topic_notes
        section = topic_notes.split(marker, 1)[1].strip()
        next_section = section.find("\n### ")
        return section[:next_section].strip() if next_section != -1 else section

    def _load_artifact_questions(self, user_id: str, artifact: Any) -> List[Dict[str, Any]]:
        """Load canonical or legacy questions for one document artifact."""
        doc_id = self._resolve_doc_id(user_id, artifact)
        if doc_id and hasattr(self.data_service, "get_document_questions"):
            questions = self.data_service.get_document_questions(user_id, doc_id) or []
            if questions:
                return questions

        topic = (artifact.topic or "").strip()
        doc_name = self.document_resolver.artifact_doc_name(artifact)
        if not topic or not doc_name:
            return []

        index_data = self.data_service.get_topic_index(user_id, topic)
        if not isinstance(index_data, dict):
            return []

        doc_prefixes = {f"{doc_name}.md#", f"{Path(doc_name).stem}.md#"}
        return [
            question
            for question in index_data.get("questions", []) or []
            if any(str(question.get("id", "") or "").startswith(prefix) for prefix in doc_prefixes)
        ]

    def _document_lines_for_artifacts(self, artifacts: List[Any]) -> List[str]:
        """Render deduplicated document lines from uploaded-source and notes artifacts."""
        by_source_path: Dict[str, Any] = {}
        no_path: List[Any] = []
        for artifact in artifacts:
            if artifact.artifact_type.value not in {"uploaded_source", "notes"}:
                continue
            source_path = artifact.source_path or (artifact.metadata or {}).get("doc_name", "")
            if not source_path:
                no_path.append(artifact)
                continue
            existing = by_source_path.get(source_path)
            if not existing or artifact.artifact_type.value == "uploaded_source":
                by_source_path[source_path] = artifact

        lines: List[str] = []
        for source_path, artifact in by_source_path.items():
            title = artifact.title or (artifact.metadata or {}).get("source_label") or source_path
            suffix = f" (`{source_path}`)" if source_path else ""
            lines.append(f"  - {title}{suffix}")
        for artifact in no_path:
            title = artifact.title or (artifact.metadata or {}).get("source_label")
            if title:
                lines.append(f"  - {title}")
        return lines

    def _note_preview_lines(self, notes: str) -> List[str]:
        """Extract a short readable preview from saved notes."""
        preview_lines: List[str] = []
        for raw_line in notes.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                preview_lines.append(f"  - {line.lstrip('#').strip()}")
            elif line.startswith("- "):
                preview_lines.append(f"  - {line[2:].strip()}")
            elif len(line) > 40 and not line.startswith("|"):
                preview_lines.append(f"  - {line[:180].strip()}")
            if len(preview_lines) >= 5:
                break
        return preview_lines or ["  - I found notes, but they do not have an easy preview shape yet."]

    def _looks_like_specific_material_lookup(self, user_input: str) -> bool:
        """Return True when the learner is checking whether a named item exists."""
        lowered = user_input.lower()
        general_inventory_phrases = (
            "any materials",
            "materials already",
            "materials do i have",
            "what materials",
            "which materials",
            "what other papers",
            "what papers",
            "papers you have",
            "what documents",
            "what files",
            "what topics",
            "list materials",
            "list topics",
        )
        if any(phrase in lowered for phrase in general_inventory_phrases):
            return False

        lookup_phrases = (
            "what about",
            "do you have",
            "have you saved",
            "did i upload",
            "i uploaded",
            "i have uploaded",
        )
        material_terms = ("paper", "article", "document", "file", "topic", "material")
        return any(phrase in lowered for phrase in lookup_phrases) and any(
            term in lowered for term in material_terms
        )

    def _requested_material_label(self, user_input: str, topics: List[str]) -> str:
        """Extract a likely missing material label from an inventory turn."""
        lowered = user_input.lower()
        topic_words = {
            word
            for topic in topics
            for word in topic.lower().replace("-", " ").replace("_", " ").split()
        }
        stop_words = {
            "what",
            "about",
            "which",
            "other",
            "papers",
            "paper",
            "article",
            "articles",
            "document",
            "documents",
            "file",
            "files",
            "material",
            "materials",
            "topic",
            "topics",
            "that",
            "this",
            "have",
            "has",
            "uploaded",
            "upload",
            "saved",
            "available",
            "explanation",
            "quiz",
            "you",
            "your",
            "for",
            "the",
            "and",
            "already",
            "any",
        }
        candidates = [
            token
            for token in lowered.replace("-", " ").replace("_", " ").replace("?", " ").split()
            if len(token) >= 5 and token not in stop_words and token not in topic_words
        ]
        return candidates[0] if candidates else ""

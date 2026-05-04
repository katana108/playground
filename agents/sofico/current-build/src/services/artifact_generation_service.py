"""Regenerate notes and review artifacts from an existing saved document."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from orchestrator.document_manifest import (
    build_document_manifest,
    build_topic_document_entry,
    extract_learning_notes,
)
from orchestrator.models import StudyArtifactType
from services.document_parser_service import DocumentParserService

logger = logging.getLogger(__name__)


class ArtifactGenerationService:
    """Rebuild note/question artifacts from one canonical saved document."""

    def __init__(self, data_service: Any, artifact_store: Any):
        self.data_service = data_service
        self.artifact_store = artifact_store
        self.parser = DocumentParserService()

    def regenerate_for_artifact(
        self,
        user_id: str,
        artifact: Any,
        *,
        regenerate_notes: bool = True,
        regenerate_questions: bool = True,
    ) -> Dict[str, Any]:
        """Refresh saved learning artifacts for one existing document."""
        doc_id = str((artifact.metadata or {}).get("doc_id", "") or "").strip()
        manifest = self.data_service.get_document_manifest(user_id, doc_id) if doc_id else {}

        topic = self._primary_topic(manifest, artifact)
        doc_name = self._doc_name(manifest, artifact)
        if not topic or not doc_name:
            return {
                "status": "error",
                "message": "I could not determine which saved document to refresh.",
            }

        source_content = self._source_content(user_id, doc_id, topic, doc_name)
        if not source_content.strip():
            return {
                "status": "error",
                "message": "I found the document, but I do not have enough source text saved to regenerate it cleanly.",
            }

        parsed = self.parser.parse_document(
            content=source_content,
            user_id=user_id,
            topic_hint=doc_name,
            data_service=self.data_service,
        )

        refreshed_notes = extract_learning_notes(parsed["study_document"]).strip()
        refreshed_questions = list(parsed.get("questions", []) or [])

        existing_notes = self._existing_notes(user_id, doc_id, topic, doc_name).strip()
        existing_questions = self._existing_questions(user_id, doc_id, topic, doc_name)

        final_notes = refreshed_notes if regenerate_notes or not existing_notes else existing_notes
        final_questions = refreshed_questions if regenerate_questions or not existing_questions else existing_questions
        study_document = self._build_study_document(final_notes, final_questions)

        new_manifest = build_document_manifest(
            parsed_result=parsed,
            raw_source_content=source_content,
            folder_topic=topic,
            doc_name=doc_name,
        )
        if manifest.get("doc_id"):
            new_manifest["doc_id"] = manifest["doc_id"]

        if hasattr(self.data_service, "save_document_bundle"):
            self.data_service.save_document_bundle(
                user_id,
                new_manifest,
                source_content,
                final_notes,
                final_questions,
            )

        topic_memberships = self._topic_memberships(new_manifest, manifest, artifact)
        for membership in topic_memberships:
            self.data_service.save_study_document(user_id, membership, doc_name, study_document)
            self._replace_topic_index(
                user_id=user_id,
                topic=membership,
                doc_name=doc_name,
                questions=final_questions,
                tags=list(parsed.get("tags", []) or []),
                document_entry=build_topic_document_entry(new_manifest),
            )

        self._upsert_registry_artifacts(
            user_id=user_id,
            topic_memberships=topic_memberships,
            doc_name=doc_name,
            manifest=new_manifest,
            question_count=len(final_questions),
            tags=list(parsed.get("tags", []) or []),
        )

        refreshed_parts: List[str] = []
        if regenerate_notes:
            refreshed_parts.append("notes")
        if regenerate_questions:
            refreshed_parts.append("questions")
        if not refreshed_parts:
            refreshed_parts = ["study materials"]

        return {
            "status": "saved",
            "doc_id": new_manifest.get("doc_id", ""),
            "topic": topic,
            "doc_name": doc_name,
            "question_count": len(final_questions),
            "refreshed_parts": refreshed_parts,
            "message": f"Refreshed the {', '.join(refreshed_parts)} for *{self._display_title(new_manifest, artifact)}*.",
        }

    def _source_content(self, user_id: str, doc_id: str, topic: str, doc_name: str) -> str:
        """Load canonical source, falling back to the legacy topic document if needed."""
        source_content = ""
        if doc_id and hasattr(self.data_service, "get_document_source"):
            source_content = self.data_service.get_document_source(user_id, doc_id) or ""
        if source_content.strip():
            return source_content
        if hasattr(self.data_service, "get_study_document_content"):
            return self.data_service.get_study_document_content(user_id, topic, doc_name) or ""
        return ""

    def _existing_notes(self, user_id: str, doc_id: str, topic: str, doc_name: str) -> str:
        """Load existing notes from canonical or legacy storage."""
        if doc_id and hasattr(self.data_service, "get_document_notes"):
            notes = self.data_service.get_document_notes(user_id, doc_id) or ""
            if notes.strip():
                return notes
        if hasattr(self.data_service, "get_study_document_notes"):
            return self.data_service.get_study_document_notes(user_id, topic, doc_name) or ""
        return ""

    def _existing_questions(self, user_id: str, doc_id: str, topic: str, doc_name: str) -> List[Dict[str, Any]]:
        """Load existing questions from canonical or legacy storage."""
        if doc_id and hasattr(self.data_service, "get_document_questions"):
            questions = self.data_service.get_document_questions(user_id, doc_id) or []
            if questions:
                return questions

        index_data = self.data_service.get_topic_index(user_id, topic)
        if not isinstance(index_data, dict):
            return []
        prefixes = {f"{doc_name}.md#", f"{Path(doc_name).stem}.md#"}
        return [
            question
            for question in index_data.get("questions", []) or []
            if any(str(question.get("id", "") or "").startswith(prefix) for prefix in prefixes)
        ]

    def _topic_memberships(self, new_manifest: Dict[str, Any], existing_manifest: Dict[str, Any], artifact: Any) -> List[str]:
        """Collect all topic memberships that should receive compatibility files."""
        memberships = list((((new_manifest.get("storage") or {}).get("topic_memberships")) or []))
        memberships.extend((((existing_manifest.get("storage") or {}).get("topic_memberships")) or []))
        memberships.extend((((new_manifest.get("classification") or {}).get("topics")) or []))
        memberships.extend((((existing_manifest.get("classification") or {}).get("topics")) or []))
        if artifact.topic:
            memberships.append(artifact.topic)
        primary = self._primary_topic(new_manifest, artifact)
        if primary:
            memberships.insert(0, primary)
        ordered: List[str] = []
        seen = set()
        for item in memberships:
            clean = str(item or "").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            ordered.append(clean)
        return ordered

    def _replace_topic_index(
        self,
        *,
        user_id: str,
        topic: str,
        doc_name: str,
        questions: List[Dict[str, Any]],
        tags: List[str],
        document_entry: Dict[str, Any],
    ) -> None:
        """Replace one document's questions and metadata inside a topic index."""
        index_data = self.data_service.get_topic_index(user_id, topic) or {}
        index_data.setdefault("topic", topic)
        index_data.setdefault("questions", [])
        index_data.setdefault("documents", [])

        prefixes = {f"{doc_name}.md#", f"{Path(doc_name).stem}.md#"}
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

        documents = []
        wanted_doc_id = str(document_entry.get("doc_id", "") or "").strip()
        for existing in index_data.get("documents", []) or []:
            if not isinstance(existing, dict):
                continue
            existing_doc_id = str(existing.get("doc_id", "") or "").strip()
            if wanted_doc_id and existing_doc_id == wanted_doc_id:
                continue
            documents.append(existing)
        documents.append(document_entry)
        index_data["documents"] = documents
        index_data["last_updated"] = date.today().isoformat()
        self.data_service.update_topic_index(user_id, topic, index_data)

    def _upsert_registry_artifacts(
        self,
        *,
        user_id: str,
        topic_memberships: List[str],
        doc_name: str,
        manifest: Dict[str, Any],
        question_count: int,
        tags: List[str],
    ) -> None:
        """Keep artifact registry metadata aligned with regenerated content."""
        source_label = str((((manifest.get("source") or {}).get("source_label")) or "")).strip()
        doc_type = str(manifest.get("doc_type", "") or "").strip()
        authors = list((((manifest.get("bibliography") or {}).get("authors")) or []))
        year = ((manifest.get("bibliography") or {}).get("year"))
        summary_short = str((((manifest.get("learning") or {}).get("summary_short")) or "")).strip()

        for topic in topic_memberships:
            source_path = f"{topic}/{doc_name}.md"
            uploaded = self.artifact_store.upsert_document_artifact(
                user_id=user_id,
                artifact_type=StudyArtifactType.UPLOADED_SOURCE,
                title=source_label or doc_name,
                topic=topic,
                source_path=source_path,
                metadata={
                    "source_label": source_label or doc_name,
                    "source_kind": "ingested_material",
                    "doc_name": doc_name,
                    "doc_id": manifest.get("doc_id", ""),
                    "doc_type": doc_type,
                    "authors": authors,
                    "year": year,
                },
            )
            notes = self.artifact_store.upsert_document_artifact(
                user_id=user_id,
                artifact_type=StudyArtifactType.NOTES,
                title=doc_name,
                topic=topic,
                source_path=source_path,
                metadata={
                    "tags": list(tags),
                    "question_count": question_count,
                    "doc_id": manifest.get("doc_id", ""),
                    "summary_short": summary_short,
                    "authors": authors,
                    "year": year,
                    "doc_type": doc_type,
                },
            )
            self.artifact_store.upsert_document_artifact(
                user_id=user_id,
                artifact_type=StudyArtifactType.QUESTION_SET,
                title=f"{doc_name} questions",
                topic=topic,
                source_path=source_path,
                source_artifact_id=notes.artifact_id or uploaded.artifact_id,
                metadata={
                    "question_count": question_count,
                    "tags": list(tags),
                    "doc_id": manifest.get("doc_id", ""),
                    "doc_type": doc_type,
                },
            )

    def _build_study_document(self, notes: str, questions: List[Dict[str, Any]]) -> str:
        """Reconstruct the compatibility markdown document from notes + questions."""
        notes_block = (notes or "").strip()
        question_block = self._render_question_section(questions).strip()
        if not question_block:
            return notes_block
        if not notes_block:
            return question_block
        return f"{notes_block}\n\n---\n\n{question_block}"

    def _render_question_section(self, questions: List[Dict[str, Any]]) -> str:
        """Render stored question records back into the markdown question format."""
        ordered_categories = ["Recall", "Explain", "Apply", "Connect"]
        by_category: Dict[str, List[Dict[str, Any]]] = {name: [] for name in ordered_categories}
        for question in questions:
            category = str(question.get("category") or question.get("type") or "").strip().title()
            if category not in by_category:
                by_category.setdefault(category, [])
            by_category[category].append(question)

        lines = ["## Anki Questions", ""]
        question_number = 1
        for category in ordered_categories:
            category_questions = by_category.get(category, [])
            if not category_questions:
                continue
            lines.append(f"### {category}")
            lines.append("")
            for question in category_questions:
                text = str(question.get("text") or "").strip()
                answer = str(question.get("answer") or "").strip()
                if not text or not answer:
                    continue
                lines.append(f"**Q{question_number}:** {text}")
                lines.append(f"**A{question_number}:** {answer}")
                lines.append("")
                question_number += 1
        return "\n".join(lines).rstrip()

    def _primary_topic(self, manifest: Dict[str, Any], artifact: Any) -> str:
        """Resolve the primary topic membership for one document."""
        storage = manifest.get("storage") or {}
        return str(storage.get("primary_topic") or artifact.topic or "").strip()

    def _doc_name(self, manifest: Dict[str, Any], artifact: Any) -> str:
        """Resolve the legacy topic-document stem for compatibility files."""
        storage = manifest.get("storage") or {}
        legacy_path = str(storage.get("legacy_topic_document_path") or artifact.source_path or "").strip()
        if not legacy_path:
            return ""
        name = Path(legacy_path).name
        return name[:-3] if name.endswith(".md") else name

    def _display_title(self, manifest: Dict[str, Any], artifact: Any) -> str:
        """Return the most human-readable title available."""
        return (
            str(manifest.get("display_title") or manifest.get("title") or "").strip()
            or artifact.title
            or self._doc_name(manifest, artifact)
            or "this document"
        )

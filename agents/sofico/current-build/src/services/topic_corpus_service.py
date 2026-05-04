"""Topic-scoped document corpus helpers for Sofico."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TopicCorpusDocument:
    """One canonical document inside a topic-scoped study corpus."""

    doc_id: str
    title: str
    topic: str
    doc_name: str = ""
    doc_type: str = ""
    authors: List[str] = field(default_factory=list)
    year: int | None = None
    summary_short: str = ""
    notes: str = ""
    questions: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class TopicCorpus:
    """A topic treated as a coherent set of saved documents."""

    topic: str
    documents: List[TopicCorpusDocument] = field(default_factory=list)

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def question_count(self) -> int:
        return sum(len(document.questions) for document in self.documents)


class TopicCorpusService:
    """Build topic-scoped corpora from canonical documents plus topic schedules."""

    def __init__(self, data_service: Any):
        self.data_service = data_service

    def load_corpus(self, user_id: str, topic: str) -> TopicCorpus:
        """Load all saved documents that belong to one topic."""
        clean_topic = str(topic or "").strip()
        if not clean_topic:
            return TopicCorpus(topic="")

        manifests = list(self.data_service.get_topic_document_manifests(user_id, clean_topic) or [])
        index_data = self.data_service.get_topic_index(user_id, clean_topic) or {}
        index_questions = list(index_data.get("questions", []) or [])
        documents: List[TopicCorpusDocument] = []

        if manifests:
            for manifest in manifests:
                doc_id = str(manifest.get("doc_id", "") or "").strip()
                doc_name = self._doc_name(manifest)
                notes = self._document_notes(user_id, doc_id, clean_topic, doc_name)
                summary_short = str((((manifest.get("learning") or {}).get("summary_short")) or "")).strip()
                documents.append(
                    TopicCorpusDocument(
                        doc_id=doc_id,
                        title=str(manifest.get("display_title") or manifest.get("title") or doc_name or doc_id or "untitled").strip(),
                        topic=clean_topic,
                        doc_name=doc_name,
                        doc_type=str(manifest.get("doc_type") or "").strip(),
                        authors=list((((manifest.get("bibliography") or {}).get("authors")) or [])),
                        year=((manifest.get("bibliography") or {}).get("year")),
                        summary_short=summary_short or self._summary_from_notes(notes),
                        notes=notes,
                        questions=self._questions_for_document(
                            user_id=user_id,
                            doc_id=doc_id,
                            topic=clean_topic,
                            doc_name=doc_name,
                            index_questions=index_questions,
                        ),
                        tags=list((((manifest.get("knowledge") or {}).get("keywords")) or [])),
                    )
                )
        else:
            documents = self._legacy_documents_from_topic_index(
                user_id=user_id,
                topic=clean_topic,
                index_questions=index_questions,
            )

        documents.sort(key=lambda item: (item.year or 0, item.title.lower()), reverse=True)
        return TopicCorpus(topic=clean_topic, documents=documents)

    def review_questions(
        self,
        user_id: str,
        topic: str,
        *,
        due_only: bool = True,
        category_filter: str = "",
    ) -> List[Dict[str, Any]]:
        """Return topic-scoped review questions across all documents in a corpus."""
        corpus = self.load_corpus(user_id, topic)
        questions: List[Dict[str, Any]] = []
        today = date.today().isoformat()
        wanted_category = str(category_filter or "").strip().lower()

        for document in corpus.documents:
            for question in document.questions:
                category = str(question.get("category") or question.get("type") or "").strip().lower()
                if wanted_category and category != wanted_category:
                    continue
                next_review = question.get("next_review")
                if due_only and next_review is not None and str(next_review) > today:
                    continue
                payload = dict(question)
                payload.setdefault("topic", topic)
                payload.setdefault("category", question.get("type", "Recall"))
                payload.setdefault("document_title", document.title)
                payload.setdefault("doc_id", document.doc_id)
                questions.append(payload)
        return questions

    def topic_titles(self, corpus: TopicCorpus, limit: int = 8) -> List[str]:
        """Return the human-readable document titles inside one corpus."""
        return [document.title for document in corpus.documents[:limit]]

    def resolve_topic(self, user_id: str, raw_topic: str) -> str:
        """Prefer an existing topic name when the input only approximately matches it."""
        clean = str(raw_topic or "").strip()
        if not clean:
            return ""
        available = list(self.data_service.get_available_topics(user_id) or [])
        lowered = clean.lower()
        normalized = lowered.replace("-", " ").replace("_", " ")
        for topic in available:
            topic_norm = topic.lower().replace("-", " ").replace("_", " ")
            if topic.lower() == lowered or topic_norm == normalized:
                return topic
        for topic in available:
            topic_norm = topic.lower().replace("-", " ").replace("_", " ")
            if lowered in topic.lower() or normalized in topic_norm:
                return topic
        return clean

    def _questions_for_document(
        self,
        *,
        user_id: str,
        doc_id: str,
        topic: str,
        doc_name: str,
        index_questions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Return scheduled questions for one document, falling back to canonical questions."""
        prefixes = self._question_prefixes(doc_name)
        matched = [
            dict(question)
            for question in index_questions
            if any(str(question.get("id", "") or "").startswith(prefix) for prefix in prefixes)
        ]
        if matched:
            return matched

        if doc_id and hasattr(self.data_service, "get_document_questions"):
            questions = list(self.data_service.get_document_questions(user_id, doc_id) or [])
            for question in questions:
                question.setdefault("topic", topic)
            return questions
        return []

    def _legacy_documents_from_topic_index(
        self,
        *,
        user_id: str,
        topic: str,
        index_questions: List[Dict[str, Any]],
    ) -> List[TopicCorpusDocument]:
        """Fallback when a topic has legacy files but no canonical manifests yet."""
        documents: List[TopicCorpusDocument] = []
        for filename in list(self.data_service.list_topic_documents(user_id, topic) or []):
            doc_name = filename[:-3] if filename.endswith(".md") else filename
            notes = self.data_service.get_study_document_notes(user_id, topic, doc_name) or ""
            prefixes = self._question_prefixes(doc_name)
            questions = [
                dict(question)
                for question in index_questions
                if any(str(question.get("id", "") or "").startswith(prefix) for prefix in prefixes)
            ]
            documents.append(
                TopicCorpusDocument(
                    doc_id="",
                    title=doc_name,
                    topic=topic,
                    doc_name=doc_name,
                    summary_short=self._summary_from_notes(notes),
                    notes=notes,
                    questions=questions,
                )
            )
        return documents

    def _document_notes(self, user_id: str, doc_id: str, topic: str, doc_name: str) -> str:
        """Load canonical notes, falling back to the topic-scoped compatibility file."""
        if doc_id and hasattr(self.data_service, "get_document_notes"):
            notes = self.data_service.get_document_notes(user_id, doc_id) or ""
            if notes.strip():
                return notes
        if topic and doc_name and hasattr(self.data_service, "get_study_document_notes"):
            return self.data_service.get_study_document_notes(user_id, topic, doc_name) or ""
        return ""

    def _doc_name(self, manifest: Dict[str, Any]) -> str:
        """Extract the legacy topic document stem from a canonical manifest."""
        storage = manifest.get("storage") or {}
        legacy_path = str(storage.get("legacy_topic_document_path") or "").strip()
        if not legacy_path:
            return ""
        name = Path(legacy_path).name
        return name[:-3] if name.endswith(".md") else name

    def _question_prefixes(self, doc_name: str) -> List[str]:
        """Return the possible question-id prefixes for one document."""
        stem = Path(doc_name).stem
        names = {doc_name, stem}
        return [f"{name}.md#" for name in names if name]

    def _summary_from_notes(self, notes: str) -> str:
        """Fall back to the first note paragraph when no explicit summary exists."""
        clean = (notes or "").strip()
        if not clean:
            return ""
        first = clean.split("\n\n", 1)[0].strip()
        return first[:280] + ("..." if len(first) > 280 else "")

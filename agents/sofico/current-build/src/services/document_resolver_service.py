"""Shared document-resolution helpers for Sofico runtime paths.

A resolver turns human references like "this paper" or "Ward" into one exact
saved artifact/document when possible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from orchestrator.artifact_store import ArtifactStore
from orchestrator.models import CurrentFocus, FocusKind


class DocumentResolverService:
    """Resolve and rank saved document artifacts for one learner."""

    def __init__(self, artifact_store: ArtifactStore):
        self.artifact_store = artifact_store

    def focused_artifact(self, user_id: str, focus: CurrentFocus) -> Optional[Any]:
        """Return the focused artifact if it still exists."""
        if focus.kind != FocusKind.ARTIFACT or not focus.artifact_id:
            return None
        for artifact in self.artifact_store.list_artifacts(user_id):
            if artifact.artifact_id == focus.artifact_id:
                return artifact
        return None

    def artifact_doc_name(self, artifact: Any) -> str:
        """Resolve the document filename stem from artifact metadata."""
        raw = (
            (artifact.metadata or {}).get("doc_name")
            or artifact.source_path
            or (artifact.metadata or {}).get("source_path")
            or ""
        )
        if not raw:
            return ""
        name = Path(str(raw)).name
        return name[:-3] if name.endswith(".md") else name

    def artifact_title(self, artifact: Any) -> str:
        """Return a readable document title."""
        return (
            artifact.title
            or (artifact.metadata or {}).get("source_label")
            or self.artifact_doc_name(artifact)
            or artifact.topic
            or "the saved document"
        )

    def matching_artifacts(self, user_id: str, user_input: str) -> List[Any]:
        """Find artifacts whose title/path best match the learner's words."""
        query_terms = self._artifact_query_terms(user_input)
        if not query_terms:
            return []

        searchable_types = {"uploaded_source", "notes", "lesson_material", "course_plan"}
        scored_matches = []
        for artifact in self.artifact_store.list_artifacts(user_id):
            if artifact.artifact_type.value not in searchable_types:
                continue

            meta = artifact.metadata or {}
            authors_str = " ".join(meta.get("authors") or [])
            named_people_str = " ".join(meta.get("named_people") or [])
            keywords_str = " ".join(meta.get("keywords") or [])
            key_concepts_str = " ".join(meta.get("key_concepts") or [])
            disciplines_str = " ".join(meta.get("disciplines") or [])
            schools_str = " ".join(meta.get("schools_of_thought") or [])
            year_val = meta.get("year")
            year_str = str(year_val) if year_val is not None else ""
            # Fields are ordered highest-weight first: the inner loop breaks on
            # the first match per term, so ordering determines which weight wins
            # when a term appears in multiple fields.
            weighted_fields = [
                (artifact.title, 4),
                (meta.get("source_label"), 4),
                (authors_str, 4),
                (named_people_str, 3),
                (keywords_str, 3),
                (artifact.source_path, 3),
                (meta.get("doc_name"), 3),
                (key_concepts_str, 2),
                (year_str, 2),
                (disciplines_str, 1),
                (schools_str, 1),
                (artifact.topic, 1),
            ]
            score = 0
            for term in query_terms:
                for value, weight in weighted_fields:
                    if term in str(value or "").lower():
                        score += weight
                        break
            if score:
                scored_matches.append((score, artifact))

        scored_matches.sort(
            key=lambda item: (
                -item[0],
                item[1].artifact_type.value != "uploaded_source",
                item[1].created_at or "",
            )
        )
        return [artifact for _, artifact in scored_matches]

    def select_document_artifact(self, artifacts: List[Any]) -> Optional[Any]:
        """Pick the best document-like artifact from a candidate list.

        The input list is already score-sorted by matching_artifacts — preserve
        that order within each type bucket so relevance wins over title length.
        """
        if not artifacts:
            return None
        type_rank = {
            "uploaded_source": 0,
            "notes": 1,
            "lesson_material": 2,
            "course_plan": 3,
        }
        candidates = [
            (i, artifact)
            for i, artifact in enumerate(artifacts)
            if artifact.artifact_type.value in type_rank and self.artifact_doc_name(artifact)
        ]
        if not candidates:
            return None
        # Sort by type first, then by original position (= relevance score from caller).
        return sorted(
            candidates,
            key=lambda pair: (type_rank.get(pair[1].artifact_type.value, 99), pair[0]),
        )[0][1]

    def resolve_for_review(
        self,
        user_id: str,
        user_input: str,
        focus: CurrentFocus,
    ) -> Optional[Any]:
        """Resolve a document-scoped quiz target."""
        lowered = user_input.lower()
        review_signals = (
            "quiz",
            "question",
            "questions",
            "ask me",
            "test me",
            "review",
        )
        corpus_signals = (
            "all papers",
            "all documents",
            "these papers",
            "these documents",
            "my papers",
            "my documents",
            " papers",
            " documents",
        )
        document_narrowing_signals = (
            "only this paper",
            "only about this paper",
            "just this paper",
            "just this document",
            "questions for this paper",
            "ask questions about this",
        )

        selected = self.select_document_artifact(self.matching_artifacts(user_id, user_input))
        if selected and (
            any(signal in lowered for signal in review_signals)
            or any(signal in lowered for signal in document_narrowing_signals)
        ) and not any(signal in lowered for signal in corpus_signals):
            return selected

        focused = self.focused_artifact(user_id, focus)
        if not focused:
            return None

        document_signals = (
            "this paper",
            "this document",
            "this article",
            "this",
            "it",
            "only",
            "just",
            "now",
        )
        if (
            any(signal in lowered for signal in review_signals)
            or any(signal in lowered for signal in document_narrowing_signals)
            or any(signal in lowered for signal in document_signals)
        ):
            return focused
        return None

    def resolve_for_explanation(
        self,
        user_id: str,
        user_input: str,
        focus: CurrentFocus,
        target: Optional[Dict[str, Any]] = None,
        references_current_material: bool = False,
        bare_explain_request: bool = False,
    ) -> Optional[Any]:
        """Resolve a document-scoped explanation target.

        Resolution order: LLM hint → raw text match → current focus.
        Hint comes first because user messages often contain words from topic
        names or other papers that cause raw matching to return the wrong paper.
        """
        if target:
            hint = str(
                (target.get("document_hint") or target.get("artifact_hint") or target.get("topic") or "")
            ).strip()
            if hint:
                hinted = self.select_document_artifact(self.matching_artifacts(user_id, hint))
                if hinted:
                    return hinted

        selected = self.select_document_artifact(self.matching_artifacts(user_id, user_input))
        if selected:
            return selected

        focused = self.focused_artifact(user_id, focus)
        if not focused:
            return None

        lowered = user_input.lower()
        if (
            bare_explain_request
            or references_current_material
            or any(
                token in lowered
                for token in ("this", "it", "that", "article", "paper", "text", "notes", "yes", "go on", "continue", "say more")
            )
        ):
            return focused
        return None

    def resolve_requested_artifact(
        self,
        user_id: str,
        user_input: str,
        focus: CurrentFocus,
        *,
        explicit_topic: Optional[str] = None,
        exact_notes_request: bool = False,
        exact_question_request: bool = False,
        references_current_material: bool = False,
    ) -> Optional[Any]:
        """Resolve the exact document implied by an artifact-inspection request."""
        selected = self.select_document_artifact(self.matching_artifacts(user_id, user_input))
        if selected:
            return selected

        if explicit_topic:
            return None

        focused = self.focused_artifact(user_id, focus)
        if not focused:
            return None

        lowered = user_input.lower()
        # Fall back to focused only for bare requests with no named document.
        # "show me notes for Ward" names a document — if it wasn't found above,
        # returning the wrong focused artifact is worse than returning nothing.
        bare_request = lowered.strip() in {
            "show notes", "show me notes", "show me the notes", "notes",
            "show questions", "show me questions", "show me the questions",
            "show the questions", "show the notes",
        }
        if (
            (bare_request and (exact_notes_request or exact_question_request))
            or references_current_material
        ):
            return focused
        return None

    def extract_topic_reference(self, user_input: str, available_topics: List[str]) -> Optional[str]:
        """Return a topic only when the learner explicitly names it."""
        lowered = user_input.lower()
        for topic in available_topics:
            normalized = topic.lower().replace("-", " ").replace("_", " ")
            if topic.lower() in lowered or normalized in lowered:
                return topic
        return None

    def _artifact_query_terms(self, user_input: str) -> List[str]:
        """Extract the content words most useful for artifact matching."""
        stop_words = {
            "what",
            "about",
            "there",
            "is",
            "are",
            "another",
            "other",
            "paper",
            "papers",
            "document",
            "documents",
            "folder",
            "that",
            "this",
            "the",
            "in",
            "it",
            "do",
            "you",
            "not",
            "see",
            "title",
            "have",
            "has",
            "with",
            "for",
            "look",
            "into",
            "says",
            "said",
            "asked",
            "ask",
            "answer",
            "answers",
            "question",
            "questions",
            "exactly",
            "give",
            "gives",
            "rise",
            "arise",
            "arises",
            "notes",
            "summary",
            "show",
            "explain",
            "quiz",
            "review",
            "make",
            "create",
            "generate",
            "study",
            "artifacts",
            "materials",
            "move",
            "rename",
            "delete",
            "from",
            "topic",
            "topics",
            "please",
            "want",
            "save",
            "saved",
            "file",
            "files",
            "find",
        }
        normalized = (
            user_input.lower()
            .replace("-", " ")
            .replace("_", " ")
            .replace("?", " ")
            .replace(",", " ")
            .replace(".", " ")
        )
        terms: List[str] = []
        for token in normalized.split():
            if len(token) < 4 or token in stop_words:
                continue
            terms.append(token)
            if len(token) >= 10:
                terms.append(token[:12])
                terms.append(token[:-3])
        return list(dict.fromkeys(term for term in terms if len(term) >= 4))

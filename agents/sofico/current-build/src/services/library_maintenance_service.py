"""Repair and dedupe helpers for Sofico's document library."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Tuple

from orchestrator.document_manifest import build_topic_document_entry
from orchestrator.models import StudyArtifact
from services.topic_corpus_service import TopicCorpusService


class LibraryMaintenanceService:
    """Rebuild topic indexes and remove safe duplicate registry entries."""

    def __init__(self, data_service: Any, artifact_store: Any, topic_corpus_service: TopicCorpusService):
        self.data_service = data_service
        self.artifact_store = artifact_store
        self.topic_corpus_service = topic_corpus_service

    def repair_library(self, user_id: str, topic: str = "") -> Dict[str, Any]:
        """Repair topic indexes, rename garbled slugs, and dedupe artifacts."""
        renamed_topics = self._fix_garbled_topic_slugs(user_id) if not topic else []
        topics = [topic] if topic else self._all_topics(user_id)
        repaired_topics = 0
        added_questions = 0
        removed_duplicate_artifacts = 0
        fixed_documents = 0

        for current_topic in topics:
            if not current_topic:
                continue
            topic_result = self._repair_topic(user_id, current_topic)
            if topic_result["changed"]:
                repaired_topics += 1
            added_questions += topic_result["added_questions"]
            fixed_documents += topic_result["document_count"]

        artifacts = self.artifact_store.list_artifacts(user_id)
        deduped_artifacts, removed_duplicate_artifacts = self._dedupe_exact_artifacts(artifacts)
        if removed_duplicate_artifacts:
            self.artifact_store.save_artifacts(user_id, deduped_artifacts)

        if not repaired_topics and not removed_duplicate_artifacts and not renamed_topics:
            scope_text = f" under *{topic}*" if topic else ""
            return {
                "status": "noop",
                "message": f"I checked your library{scope_text} and did not find anything that needed repair.",
            }

        scope_text = f" under *{topic}*" if topic else ""
        rename_note = ""
        if renamed_topics:
            rename_note = " Renamed garbled topic folders: " + ", ".join(
                f"{old} → {new}" for old, new in renamed_topics
            ) + "."
        return {
            "status": "ok",
            "message": (
                f"Repaired your document library{scope_text}: "
                f"{repaired_topics} topics refreshed, "
                f"{fixed_documents} documents re-indexed, "
                f"{added_questions} missing questions restored, "
                f"{removed_duplicate_artifacts} duplicate artifact entries removed."
                + rename_note
            ),
        }

    def _repair_topic(self, user_id: str, topic: str) -> Dict[str, Any]:
        """Refresh one topic index from canonical manifests plus existing schedules."""
        manifests = list(self.data_service.get_topic_document_manifests(user_id, topic) or [])
        if not manifests:
            return {"changed": False, "added_questions": 0, "document_count": 0}

        index_data = self.data_service.get_topic_index(user_id, topic) or {}
        existing_questions = list(index_data.get("questions", []) or [])
        existing_by_id = {
            str(question.get("id", "") or ""): dict(question)
            for question in existing_questions
            if question.get("id")
        }
        merged_questions: List[Dict[str, Any]] = []
        added_questions = 0

        for manifest in manifests:
            doc_id = str(manifest.get("doc_id", "") or "").strip()
            canonical_questions = list(self.data_service.get_document_questions(user_id, doc_id) or [])
            for question in canonical_questions:
                qid = str(question.get("id", "") or "").strip()
                if not qid:
                    continue
                if qid in existing_by_id:
                    merged_questions.append(existing_by_id[qid])
                else:
                    payload = dict(question)
                    payload.setdefault("topic", topic)
                    merged_questions.append(payload)
                    added_questions += 1

        documents = [build_topic_document_entry(manifest) for manifest in manifests]
        merged_questions.sort(key=lambda question: str(question.get("id", "") or ""))
        documents.sort(key=lambda item: str(item.get("display_title") or item.get("title") or ""))

        changed = (
            documents != list(index_data.get("documents", []) or [])
            or merged_questions != existing_questions
        )

        if changed:
            self.data_service.update_topic_index(
                user_id,
                topic,
                {
                    "topic": topic,
                    "last_updated": date.today().isoformat(),
                    "questions": merged_questions,
                    "documents": documents,
                },
            )

        return {
            "changed": changed,
            "added_questions": added_questions,
            "document_count": len(documents),
        }

    def _dedupe_exact_artifacts(self, artifacts: List[StudyArtifact]) -> Tuple[List[StudyArtifact], int]:
        """Remove only exact duplicate artifact rows with the same identity tuple."""
        kept: List[StudyArtifact] = []
        seen = set()
        removed = 0
        for artifact in artifacts:
            key = (
                artifact.artifact_type.value,
                str((artifact.metadata or {}).get("doc_id", "") or "").strip(),
                str(artifact.topic or "").strip(),
                str(artifact.source_path or "").strip(),
                str(artifact.title or "").strip(),
            )
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            kept.append(artifact)
        return kept, removed

    def _fix_garbled_topic_slugs(self, user_id: str) -> List[tuple]:
        """Rename topic folders whose names are longer than 60 chars (LLM reasoning leaks)."""
        if not hasattr(self.data_service, "rename_topic_folder"):
            return []
        topics = list(self.data_service.get_available_topics(user_id) or [])
        renamed = []
        for topic in topics:
            if len(topic) <= 60:
                continue
            # Sanitize: keep only valid slug chars, cap at 5 words
            slug = re.sub(r"[^a-z0-9\-]", "-", topic.lower())
            slug = re.sub(r"-{2,}", "-", slug).strip("-")
            words = [w for w in slug.split("-") if w][:5]
            clean = "-".join(words) if words else "unknown-topic"
            # Avoid clobbering an existing topic
            existing = set(topics)
            candidate = clean
            suffix = 2
            while candidate in existing:
                candidate = f"{clean}-{suffix}"
                suffix += 1
            ok = self.data_service.rename_topic_folder(user_id, topic, candidate)
            if not ok:
                continue
            # Update artifact store entries that reference the old topic name
            artifacts = self.artifact_store.list_artifacts(user_id)
            updated = False
            for artifact in artifacts:
                if artifact.topic == topic:
                    artifact.topic = candidate
                    old_sp = str(artifact.source_path or "")
                    if old_sp.startswith(f"{topic}/"):
                        artifact.source_path = candidate + old_sp[len(topic):]
                    updated = True
            if updated:
                self.artifact_store.save_artifacts(user_id, artifacts)
            renamed.append((topic[:40] + "…", candidate))
        return renamed

    def _all_topics(self, user_id: str) -> List[str]:
        """Return known topics from disk, falling back to manifests."""
        topics = list(self.data_service.get_available_topics(user_id) or [])
        if topics:
            return topics
        discovered = set()
        for manifest in self.data_service.list_document_manifests(user_id) or []:
            for item in ((manifest.get("classification") or {}).get("topics") or []):
                clean = str(item or "").strip()
                if clean:
                    discovered.add(clean)
        return sorted(discovered)

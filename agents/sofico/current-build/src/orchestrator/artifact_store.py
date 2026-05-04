"""Artifact persistence and indexing for Sofi V2.

Artifacts are the domain-knowledge objects Sofi creates or uses over time.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import yaml

from .models import StudyArtifact, StudyArtifactType


def utc_now_iso() -> str:
    """Return a stable UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ArtifactStore:
    """Persist and retrieve first-class study artifacts."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.learners_root = Path(
            os.getenv("SOFI_LEARNERS_PATH") or self.project_root / "learners"
        )

    def get_registry_path(self, user_id: str) -> Path:
        """Return the artifact registry path for one learner."""
        return self.learners_root / self._user_folder(user_id) / "artifacts.yaml"

    def _user_folder(self, user_id: str) -> str:
        """Map platform user IDs to stable learner folders when user_map.yaml exists."""
        try:
            map_path = self.learners_root / "user_map.yaml"
            if map_path.exists():
                with map_path.open("r", encoding="utf-8") as handle:
                    user_map = yaml.safe_load(handle) or {}
                return user_map.get(user_id, user_id)
        except Exception:
            return user_id
        return user_id

    def list_artifacts(self, user_id: str) -> List[StudyArtifact]:
        """Load all artifacts for a learner."""
        path = self.get_registry_path(user_id)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        raw_items = data.get("artifacts", [])
        return [self._from_dict(item) for item in raw_items if isinstance(item, dict)]

    def save_artifacts(self, user_id: str, artifacts: List[StudyArtifact]) -> Path:
        """Persist a learner artifact registry."""
        path = self.get_registry_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "metadata": {
                "schema_version": 1,
                "updated_at": utc_now_iso(),
            },
            "artifacts": [self._to_dict(artifact) for artifact in artifacts],
        }
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=False)
        return path

    def add_artifact(
        self,
        user_id: str,
        artifact_type: StudyArtifactType,
        title: str,
        topic: str = "",
        source_path: str = "",
        source_artifact_id: str = "",
        linked_plan_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StudyArtifact:
        """Append one artifact and persist the registry."""
        artifacts = self.list_artifacts(user_id)
        artifact = StudyArtifact(
            artifact_id=uuid4().hex,
            artifact_type=artifact_type,
            title=title,
            user_id=user_id,
            topic=topic,
            source_path=source_path,
            source_artifact_id=source_artifact_id,
            linked_plan_id=linked_plan_id,
            created_at=utc_now_iso(),
            metadata=metadata or {},
        )
        artifacts.append(artifact)
        self.save_artifacts(user_id, artifacts)
        return artifact

    def find_by_type(self, user_id: str, artifact_type: StudyArtifactType) -> List[StudyArtifact]:
        """Filter learner artifacts by type."""
        return [artifact for artifact in self.list_artifacts(user_id) if artifact.artifact_type == artifact_type]

    def find_by_topic(self, user_id: str, topic: str) -> List[StudyArtifact]:
        """Filter learner artifacts by topic slug/name."""
        topic_lower = topic.lower().strip()
        return [
            artifact
            for artifact in self.list_artifacts(user_id)
            if artifact.topic.lower().strip() == topic_lower
        ]

    def find_by_doc_id(self, user_id: str, doc_id: str) -> List[StudyArtifact]:
        """Return artifacts linked to one canonical document id."""
        wanted = str(doc_id or "").strip()
        if not wanted:
            return []
        return [
            artifact
            for artifact in self.list_artifacts(user_id)
            if str((artifact.metadata or {}).get("doc_id", "") or "").strip() == wanted
        ]

    def upsert_document_artifact(
        self,
        user_id: str,
        artifact_type: StudyArtifactType,
        title: str,
        topic: str = "",
        source_path: str = "",
        source_artifact_id: str = "",
        linked_plan_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StudyArtifact:
        """Update an existing document artifact or append it when missing.

        Matching prefers canonical doc_id when available, then falls back to
        type + topic + source_path. This keeps regeneration idempotent.
        """
        metadata = metadata or {}
        wanted_doc_id = str(metadata.get("doc_id", "") or "").strip()
        normalized_source = str(source_path or "").strip()
        normalized_topic = str(topic or "").strip().lower()

        artifacts = self.list_artifacts(user_id)
        match_index: Optional[int] = None
        for idx, artifact in enumerate(artifacts):
            if artifact.artifact_type != artifact_type:
                continue
            existing_doc_id = str((artifact.metadata or {}).get("doc_id", "") or "").strip()
            same_doc = bool(wanted_doc_id and existing_doc_id and existing_doc_id == wanted_doc_id)
            same_path = bool(
                normalized_source
                and normalized_topic
                and str(artifact.source_path or "").strip() == normalized_source
                and artifact.topic.lower().strip() == normalized_topic
            )
            if same_doc or same_path:
                match_index = idx
                break

        if match_index is None:
            return self.add_artifact(
                user_id=user_id,
                artifact_type=artifact_type,
                title=title,
                topic=topic,
                source_path=source_path,
                source_artifact_id=source_artifact_id,
                linked_plan_id=linked_plan_id,
                metadata=metadata,
            )

        existing = artifacts[match_index]
        existing.title = title
        existing.topic = topic
        existing.source_path = source_path
        existing.source_artifact_id = source_artifact_id or existing.source_artifact_id
        existing.linked_plan_id = linked_plan_id or existing.linked_plan_id
        existing.metadata = metadata
        artifacts[match_index] = existing
        self.save_artifacts(user_id, artifacts)
        return existing

    def _to_dict(self, artifact: StudyArtifact) -> Dict[str, Any]:
        """Serialize an artifact."""
        payload = asdict(artifact)
        payload["artifact_type"] = artifact.artifact_type.value
        return payload

    def _from_dict(self, item: Dict[str, Any]) -> StudyArtifact:
        """Deserialize an artifact."""
        return StudyArtifact(
            artifact_id=item.get("artifact_id", ""),
            artifact_type=StudyArtifactType(item.get("artifact_type", StudyArtifactType.NOTES.value)),
            title=item.get("title", ""),
            user_id=item.get("user_id", ""),
            topic=item.get("topic", ""),
            source_path=item.get("source_path", ""),
            source_artifact_id=item.get("source_artifact_id", ""),
            linked_plan_id=item.get("linked_plan_id", ""),
            created_at=item.get("created_at", ""),
            metadata=item.get("metadata", {}) or {},
        )

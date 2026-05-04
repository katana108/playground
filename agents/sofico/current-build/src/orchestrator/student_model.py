"""Student model types and persistence for Sofi V2.

This is the learner notebook for the new orchestration layer.
It is separate from Sofi's teacher identity and separate from study artifacts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import copy
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import yaml

logger = logging.getLogger(__name__)


class StudentMemoryDecision(str, Enum):
    """How a new learner observation should affect the student model."""

    ADD = "add"
    UPDATE = "update"
    NOOP = "noop"


STUDENT_MEMORY_SECTIONS = {
    "inferred_profile",
    "progress_patterns",
    "relationship_memory",
}


def utc_now_iso() -> str:
    """Return a stable UTC timestamp string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class StudentMemoryEntry:
    """One evidence-backed learner memory."""

    entry_id: str
    summary: str
    section: str = "inferred_profile"
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5
    source: str = "session_reflection"
    status: str = "active"
    superseded_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StudentMemoryUpdate:
    """Candidate mutation to the student model."""

    decision: StudentMemoryDecision
    summary: str
    section: str = "inferred_profile"
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5
    target_entry_id: str = ""
    source: str = "session_reflection"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StudentModel:
    """The learner model Sofi updates over time."""

    identity: Dict[str, Any] = field(default_factory=dict)
    goals_and_constraints: Dict[str, Any] = field(default_factory=dict)
    stated_preferences_about_self: Dict[str, Any] = field(default_factory=dict)
    inferred_profile: List[StudentMemoryEntry] = field(default_factory=list)
    progress_patterns: List[StudentMemoryEntry] = field(default_factory=list)
    relationship_memory: List[StudentMemoryEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class StudentModelStore:
    """Load, save, and revise student models on disk."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.learners_root = Path(
            os.getenv("SOFI_LEARNERS_PATH") or self.project_root / "learners"
        )

    def get_path(self, user_id: str) -> Path:
        """Return the on-disk path for a learner's student model."""
        return self.learners_root / self._user_folder(user_id) / "student_model.yaml"

    def get_learner_folder(self, user_id: str) -> str:
        """Return the canonical learner folder for a platform user id."""
        return self._user_folder(user_id)

    def load(self, user_id: str) -> StudentModel:
        """Load a student model or return a default shell."""
        path = self.get_path(user_id)
        if not path.exists():
            legacy_model = self._load_from_legacy_profile(user_id)
            if legacy_model:
                self.save(user_id, legacy_model)
                return legacy_model
            return self._default_model(user_id)

        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            return self._from_dict(data, user_id)
        except Exception as exc:
            logger.warning("Failed to load student model for %s: %s", user_id, exc)
            return self._default_model(user_id)

    def save(self, user_id: str, model: StudentModel) -> Path:
        """Persist a student model to disk."""
        path = self.get_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        model.metadata = self._merged_metadata(model.metadata, {"last_updated": utc_now_iso()})

        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(self._to_dict(model), handle, sort_keys=False, allow_unicode=False)

        return path

    def _user_folder(self, user_id: str) -> str:
        """Map platform user IDs to stable learner folders when user_map.yaml exists."""
        try:
            map_path = self.learners_root / "user_map.yaml"
            if map_path.exists():
                with map_path.open("r", encoding="utf-8") as handle:
                    user_map = yaml.safe_load(handle) or {}
                return user_map.get(user_id, user_id)
        except Exception as exc:
            logger.warning("Could not read learner user_map.yaml: %s", exc)
        return user_id

    def _load_from_legacy_profile(self, user_id: str) -> Optional[StudentModel]:
        """Create a V2 student model from the older profile.yaml when available."""
        profile_path = self.learners_root / self._user_folder(user_id) / "profile.yaml"
        if not profile_path.exists():
            return None

        try:
            with profile_path.open("r", encoding="utf-8") as handle:
                profile = yaml.safe_load(handle) or {}
        except Exception as exc:
            logger.warning("Could not import legacy profile for %s: %s", user_id, exc)
            return None

        now = utc_now_iso()
        model = self._default_model(user_id)
        metadata = profile.get("metadata", {}) or {}
        communication = profile.get("communication", {}) or {}
        explanation = profile.get("explanation_preferences", {}) or {}
        feedback = profile.get("feedback_preferences", {}) or {}
        interests = profile.get("interests", {}) or {}
        learning_level = profile.get("learning_level", {}) or {}

        learner_name = str(metadata.get("learner_name", "")).strip()
        if learner_name:
            model.identity["learner_name"] = learner_name
            model.identity["preferred_form_of_address"] = learner_name
        if learning_level:
            model.identity["topic_proficiency"] = learning_level

        raw_background = list(interests.get("background_knowledge", []) or [])
        garbage_fragments = {"start creating lessons", "quiz me", "beginner yes", "lala", "start lesson"}
        background = [
            item for item in raw_background
            if isinstance(item, str) and len(item) < 60
            and not any(frag in item.lower() for frag in garbage_fragments)
        ]
        model.goals_and_constraints["preferred_subjects"] = background or ["general learning"]
        model.goals_and_constraints["study_goals"] = ["Continue learning with Sofico"]
        model.goals_and_constraints["current_priorities"] = ["Continue learning with Sofico"]

        preferences = []
        if explanation.get("style"):
            preferences.append(f"Explanation style: {explanation['style']}")
        if communication.get("explanation_depth"):
            preferences.append(f"Explanation depth: {communication['explanation_depth']}")
        if feedback.get("style"):
            preferences.append(f"Feedback style: {feedback['style']}")
        if feedback.get("criticism_directness"):
            preferences.append(f"Correction directness: {feedback['criticism_directness']}")
        metaphor_preferences = (communication.get("metaphor_preferences", {}) or {}).get("preferred", [])
        if metaphor_preferences:
            preferences.append("Preferred metaphors: " + ", ".join(metaphor_preferences))

        model.stated_preferences_about_self["learning_preferences"] = preferences or ["Use the existing learner profile."]
        model.stated_preferences_about_self["direct_statements"] = preferences or ["Imported from existing learner profile."]
        model.metadata = self._merged_metadata(
            model.metadata,
            {
                "imported_from": "profile.yaml",
                "imported_at": now,
                "legacy_profile_path": str(profile_path),
                "requires_v2_onboarding": True,
                "legacy_profile_needs_review": True,
            },
        )
        return model

    def apply_updates(
        self,
        user_id: str,
        updates: List[StudentMemoryUpdate],
        model: Optional[StudentModel] = None,
    ) -> StudentModel:
        """Apply ADD / UPDATE / NOOP updates while preserving history."""
        working = copy.deepcopy(model or self.load(user_id))
        applied = 0

        for update in updates:
            if update.decision == StudentMemoryDecision.NOOP:
                continue

            if update.section not in STUDENT_MEMORY_SECTIONS:
                logger.warning("Ignoring student memory update with unknown section: %s", update.section)
                continue

            if update.decision == StudentMemoryDecision.ADD:
                self._append_entry(working, update)
                applied += 1
                continue

            if update.decision == StudentMemoryDecision.UPDATE:
                if not update.target_entry_id:
                    logger.warning("UPDATE missing target_entry_id; degrading to ADD")
                    self._append_entry(working, update)
                    applied += 1
                    continue
                if self._supersede_entry(working, update):
                    applied += 1
                else:
                    logger.warning("Could not find target entry %s; degrading to ADD", update.target_entry_id)
                    self._append_entry(working, update)
                    applied += 1

        working.metadata = self._merged_metadata(
            working.metadata,
            {
                "last_updated": utc_now_iso(),
                "last_update_count": applied,
            },
        )
        return working

    def _default_model(self, user_id: str) -> StudentModel:
        """Return a clean starting learner notebook."""
        now = utc_now_iso()
        return StudentModel(
            identity={
                "user_id": user_id,
                "learner_folder": self._user_folder(user_id),
            },
            goals_and_constraints={},
            stated_preferences_about_self={},
            inferred_profile=[],
            progress_patterns=[],
            relationship_memory=[],
            metadata={
                "schema_version": 1,
                "created_at": now,
                "last_updated": now,
            },
        )

    def _from_dict(self, data: Dict[str, Any], user_id: str) -> StudentModel:
        """Normalize raw YAML into a StudentModel."""
        model = self._default_model(user_id)
        model.identity = data.get("identity", model.identity)
        model.identity.setdefault("user_id", user_id)
        model.identity.setdefault("learner_folder", self._user_folder(user_id))
        model.goals_and_constraints = data.get("goals_and_constraints", {})
        model.stated_preferences_about_self = data.get("stated_preferences_about_self", {})
        model.inferred_profile = self._parse_entries(data.get("inferred_profile", []), "inferred_profile")
        model.progress_patterns = self._parse_entries(data.get("progress_patterns", []), "progress_patterns")
        model.relationship_memory = self._parse_entries(data.get("relationship_memory", []), "relationship_memory")
        model.metadata = self._merged_metadata(model.metadata, data.get("metadata", {}))
        return model

    def _parse_entries(self, raw_entries: Any, section: str) -> List[StudentMemoryEntry]:
        """Normalize a list of memory entry dicts."""
        entries: List[StudentMemoryEntry] = []
        for raw in raw_entries or []:
            if not isinstance(raw, dict):
                continue
            entries.append(
                StudentMemoryEntry(
                    entry_id=raw.get("entry_id", uuid4().hex),
                    summary=raw.get("summary", ""),
                    section=section,
                    evidence=list(raw.get("evidence", []) or []),
                    confidence=float(raw.get("confidence", 0.5)),
                    source=raw.get("source", "session_reflection"),
                    status=raw.get("status", "active"),
                    superseded_by=raw.get("superseded_by", ""),
                    created_at=raw.get("created_at", ""),
                    updated_at=raw.get("updated_at", ""),
                    metadata=raw.get("metadata", {}) or {},
                )
            )
        return entries

    def _to_dict(self, model: StudentModel) -> Dict[str, Any]:
        """Convert the student model to a YAML-safe dict."""
        return {
            "identity": model.identity,
            "goals_and_constraints": model.goals_and_constraints,
            "stated_preferences_about_self": model.stated_preferences_about_self,
            "inferred_profile": [asdict(entry) for entry in model.inferred_profile],
            "progress_patterns": [asdict(entry) for entry in model.progress_patterns],
            "relationship_memory": [asdict(entry) for entry in model.relationship_memory],
            "metadata": model.metadata,
        }

    def _append_entry(self, model: StudentModel, update: StudentMemoryUpdate) -> StudentMemoryEntry:
        """Create a fresh active memory entry."""
        now = utc_now_iso()
        entry = StudentMemoryEntry(
            entry_id=uuid4().hex,
            summary=update.summary,
            section=update.section,
            evidence=list(update.evidence),
            confidence=update.confidence,
            source=update.source,
            status="active",
            superseded_by="",
            created_at=now,
            updated_at=now,
            metadata=dict(update.metadata),
        )
        self._get_section(model, update.section).append(entry)
        return entry

    def _supersede_entry(self, model: StudentModel, update: StudentMemoryUpdate) -> bool:
        """Preserve the old memory, then append a new active revision."""
        section_entries = self._get_section(model, update.section)
        for entry in section_entries:
            if entry.entry_id != update.target_entry_id:
                continue

            replacement = self._append_entry(model, update)
            entry.status = "superseded"
            entry.superseded_by = replacement.entry_id
            entry.updated_at = replacement.created_at
            return True
        return False

    def _get_section(self, model: StudentModel, section: str) -> List[StudentMemoryEntry]:
        """Return the correct memory section list."""
        return getattr(model, section)

    def _merged_metadata(self, base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
        """Merge metadata while preserving defaults."""
        merged = dict(base or {})
        merged.update(extra or {})
        merged.setdefault("schema_version", 1)
        return merged

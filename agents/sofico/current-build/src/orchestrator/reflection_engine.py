"""Lightweight reflection engine for Sofi V2.

This first version turns session observations into student-model updates without
requiring the full dreaming system yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .student_model import (
    StudentMemoryDecision,
    StudentMemoryEntry,
    StudentMemoryUpdate,
    StudentModel,
)


@dataclass
class SessionReflectionInput:
    """Minimal structured input for one meaningful learning session."""

    user_id: str
    summary: str
    observations: List[str] = field(default_factory=list)
    explicit_preferences: List[str] = field(default_factory=list)
    progress_notes: List[str] = field(default_factory=list)
    relationship_notes: List[str] = field(default_factory=list)


class ReflectionEngine:
    """Generate first-pass learner updates from a session."""

    def should_reflect(self, session: SessionReflectionInput) -> bool:
        """Decide whether a session is meaningful enough for reflection."""
        signal_count = (
            len(session.observations)
            + len(session.explicit_preferences)
            + len(session.progress_notes)
            + len(session.relationship_notes)
        )
        return bool(session.summary.strip()) and signal_count > 0

    def reflect(
        self,
        student_model: StudentModel,
        session: SessionReflectionInput,
    ) -> List[StudentMemoryUpdate]:
        """Convert session evidence into ADD / UPDATE / NOOP updates."""
        if not self.should_reflect(session):
            return []

        updates: List[StudentMemoryUpdate] = []
        updates.extend(self._updates_for_section(student_model.inferred_profile, "inferred_profile", session.observations, session.summary))
        updates.extend(self._updates_for_section(student_model.progress_patterns, "progress_patterns", session.progress_notes, session.summary))
        updates.extend(self._updates_for_section(student_model.relationship_memory, "relationship_memory", session.relationship_notes, session.summary))
        return updates

    def _updates_for_section(
        self,
        existing_entries: List[StudentMemoryEntry],
        section: str,
        notes: List[str],
        session_summary: str,
    ) -> List[StudentMemoryUpdate]:
        """Map raw notes into updates, revising similar active memories when possible."""
        updates: List[StudentMemoryUpdate] = []
        for note in notes:
            clean_note = note.strip()
            if not clean_note:
                continue

            target = self._find_revision_target(existing_entries, clean_note)
            if target:
                updates.append(
                    StudentMemoryUpdate(
                        decision=StudentMemoryDecision.UPDATE,
                        section=section,
                        target_entry_id=target.entry_id,
                        summary=clean_note,
                        evidence=[session_summary],
                        confidence=0.75,
                        source="reflection_v1",
                    )
                )
            else:
                updates.append(
                    StudentMemoryUpdate(
                        decision=StudentMemoryDecision.ADD,
                        section=section,
                        summary=clean_note,
                        evidence=[session_summary],
                        confidence=0.72,
                        source="reflection_v1",
                    )
                )
        return updates

    def _find_revision_target(
        self,
        existing_entries: List[StudentMemoryEntry],
        note: str,
    ) -> Optional[StudentMemoryEntry]:
        """Find a likely existing entry to revise using simple token overlap."""
        note_tokens = self._meaningful_tokens(note)
        if not note_tokens:
            return None

        best_match: Optional[StudentMemoryEntry] = None
        best_overlap = 0
        for entry in existing_entries:
            if entry.status != "active":
                continue
            overlap = len(note_tokens & self._meaningful_tokens(entry.summary))
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = entry

        return best_match if best_overlap >= 2 else None

    def _meaningful_tokens(self, text: str) -> set[str]:
        """Tokenize lightly and discard very short words."""
        return {token.lower() for token in text.replace("/", " ").replace("-", " ").split() if len(token) > 3}

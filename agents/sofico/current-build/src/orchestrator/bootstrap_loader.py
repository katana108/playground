"""Bootstrap/context loading helpers for Sofi V2 orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from .student_model import StudentModel, StudentModelStore


@dataclass
class OrchestratorBootstrapContext:
    """Foundational context loaded before orchestration decisions."""

    teacher_soul: str
    teacher_model: Dict[str, Any]
    identity_text: str
    identity_defaults: Dict[str, Any]
    teaching_text: str
    teaching_defaults: Dict[str, Any]
    student_model: StudentModel


class BootstrapLoader:
    """Load stable teacher identity and per-learner student context."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        soul_path: Optional[Path] = None,
        teacher_model_path: Optional[Path] = None,
        identity_path: Optional[Path] = None,
        teaching_path: Optional[Path] = None,
        student_model_store: Optional[StudentModelStore] = None,
    ):
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        bootstrap_dir = Path(__file__).resolve().parent / "bootstrap"
        self.soul_path = soul_path or bootstrap_dir / "SOUL.md"
        self.teacher_model_path = teacher_model_path or bootstrap_dir / "teacher_model.yaml"
        self.identity_path = identity_path or bootstrap_dir / "IDENTITY.md"
        self.teaching_path = teaching_path or bootstrap_dir / "TEACHING.md"
        self.student_model_store = student_model_store or StudentModelStore(self.project_root)

    def load_teacher_soul(self) -> str:
        """Read the teacher bootstrap file."""
        return self.soul_path.read_text(encoding="utf-8").strip()

    def load_teacher_model(self) -> Dict[str, Any]:
        """Read the structured teacher system view."""
        with self.teacher_model_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def load_identity_defaults(self) -> Tuple[str, Dict[str, Any]]:
        """Read and parse the identity bootstrap file."""
        return self._load_structured_markdown(self.identity_path)

    def load_teaching_defaults(self) -> Tuple[str, Dict[str, Any]]:
        """Read and parse the teaching bootstrap file."""
        return self._load_structured_markdown(self.teaching_path)

    def load_student_model(self, user_id: str) -> StudentModel:
        """Read the per-learner student model."""
        return self.student_model_store.load(user_id)

    def save_student_model(self, user_id: str, model: StudentModel) -> Path:
        """Persist the per-learner student model."""
        return self.student_model_store.save(user_id, model)

    def load_context(self, user_id: str) -> OrchestratorBootstrapContext:
        """Return the teacher + learner context needed by the orchestrator."""
        identity_text, identity_defaults = self.load_identity_defaults()
        teaching_text, teaching_defaults = self.load_teaching_defaults()
        return OrchestratorBootstrapContext(
            teacher_soul=self.load_teacher_soul(),
            teacher_model=self.load_teacher_model(),
            identity_text=identity_text,
            identity_defaults=identity_defaults,
            teaching_text=teaching_text,
            teaching_defaults=teaching_defaults,
            student_model=self.load_student_model(user_id),
        )

    def _load_structured_markdown(self, path: Path) -> Tuple[str, Dict[str, Any]]:
        """Read a bootstrap markdown file and extract simple default fields.

        This parser is intentionally light. It supports the current bootstrap-file
        shape:

        - `field`: `value`
        - `field`:
          - `list_item`
        """
        text = path.read_text(encoding="utf-8").strip()
        parsed: Dict[str, Any] = {}
        current_list_key: Optional[str] = None

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                current_list_key = None
                continue

            if stripped.startswith("- `") and "`: `" in stripped and stripped.endswith("`"):
                current_list_key = None
                key, value = self._parse_key_value_line(stripped)
                parsed[key] = self._coerce_scalar(value)
                continue

            if stripped.startswith("- `") and stripped.endswith("`:"):
                current_list_key = stripped[3:-2]
                parsed[current_list_key] = []
                continue

            if current_list_key and stripped.startswith("- `") and stripped.endswith("`"):
                parsed[current_list_key].append(stripped[3:-1])
                continue

            if current_list_key and stripped.startswith("- "):
                parsed[current_list_key].append(stripped[2:].strip())
                continue

        return text, parsed

    def _parse_key_value_line(self, line: str) -> Tuple[str, str]:
        """Extract a backtick-wrapped key/value pair from one list line."""
        key_end = line.index("`:")
        key = line[3:key_end]
        value_start = line.index(": `") + 3
        value = line[value_start:-1]
        return key, value

    def _coerce_scalar(self, value: str) -> Any:
        """Convert simple scalar strings into bool/int when appropriate."""
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if value.isdigit():
            return int(value)
        return value

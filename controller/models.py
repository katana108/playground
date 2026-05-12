from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MessageRecord:
    role: str
    content: str
    timestamp: str = field(default_factory=iso_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessageRecord":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", iso_now()),
            metadata=data.get("metadata", {}) or {},
        )


@dataclass
class AgentDefinition:
    agent_id: str
    display_name: str
    adapter_type: str
    definition_dir: Path
    runtime_dir: Path
    notes: str = ""
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnRequest:
    agent: AgentDefinition
    prompt: str
    transcript: list[MessageRecord]
    notebook_text: str
    state: dict[str, Any]
    phase: str
    conversation_name: str
    round_name: str | None = None


@dataclass
class TurnResult:
    response_text: str
    notebook_append: str = ""
    state_patch: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

from __future__ import annotations

import json
from pathlib import Path

from .models import MessageRecord


class AgentWorkspace:
    def __init__(self, root: Path):
        self.root = root
        self.notebook_path = self.root / "notebook.md"
        self.state_path = self.root / "state.json"
        self.transcript_path = self.root / "transcript.jsonl"
        self.summary_path = self.root / "session_summary.md"

    def ensure_exists(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.notebook_path.exists():
            self.notebook_path.write_text("# Notebook\n", encoding="utf-8")
        if not self.state_path.exists():
            self.state_path.write_text("{}\n", encoding="utf-8")
        if not self.transcript_path.exists():
            self.transcript_path.write_text("", encoding="utf-8")
        if not self.summary_path.exists():
            self.summary_path.write_text("# Session Summary\n", encoding="utf-8")

    def load_notebook(self) -> str:
        self.ensure_exists()
        return self.notebook_path.read_text(encoding="utf-8")

    def append_notebook(self, text: str) -> None:
        self.ensure_exists()
        if not text.strip():
            return
        with self.notebook_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n\n{text.strip()}\n")

    def load_state(self) -> dict:
        self.ensure_exists()
        raw = self.state_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        return json.loads(raw)

    def save_state(self, state: dict) -> None:
        self.ensure_exists()
        self.state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def merge_state_patch(self, patch: dict) -> dict:
        current = self.load_state()
        current.update(patch)
        self.save_state(current)
        return current

    def load_transcript(self) -> list[MessageRecord]:
        self.ensure_exists()
        records: list[MessageRecord] = []
        for line in self.transcript_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(MessageRecord.from_dict(json.loads(line)))
        return records

    def append_message(self, message: MessageRecord) -> None:
        self.ensure_exists()
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message.to_dict(), ensure_ascii=True) + "\n")


class RoundtableWorkspace:
    def __init__(self, root: Path):
        self.root = root
        self.transcript_path = self.root / "transcript.jsonl"
        self.shared_view_path = self.root / "shared_transcript.md"

    def ensure_exists(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.transcript_path.exists():
            self.transcript_path.write_text("", encoding="utf-8")
        if not self.shared_view_path.exists():
            self.shared_view_path.write_text("# Shared Transcript\n", encoding="utf-8")

    def load_transcript(self) -> list[MessageRecord]:
        self.ensure_exists()
        records: list[MessageRecord] = []
        for line in self.transcript_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(MessageRecord.from_dict(json.loads(line)))
        return records

    def append_message(self, message: MessageRecord) -> None:
        self.ensure_exists()
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message.to_dict(), ensure_ascii=True) + "\n")
        self._rewrite_shared_view()

    def _rewrite_shared_view(self) -> None:
        lines = ["# Shared Transcript", ""]
        for item in self.load_transcript():
            label = item.metadata.get("speaker", item.role)
            round_name = item.metadata.get("round")
            if round_name:
                lines.append(f"## {round_name} · {label}")
            else:
                lines.append(f"## {label}")
            lines.append("")
            lines.append(item.content.strip())
            lines.append("")
        self.shared_view_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

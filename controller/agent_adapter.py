from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

from .corpus import load_shared_corpus
from .models import AgentDefinition, TurnRequest, TurnResult


class AgentAdapter(ABC):
    def __init__(self, definition: AgentDefinition):
        self.definition = definition

    @abstractmethod
    def run_turn(self, request: TurnRequest) -> TurnResult:
        raise NotImplementedError

    def prepare_private_prep(self, prompt: str) -> str:
        return ""


class ManualAgentAdapter(AgentAdapter):
    def run_turn(self, request: TurnRequest) -> TurnResult:
        print(f"\n[{self.definition.display_name} · manual adapter]")
        print(f"Phase: {request.phase}")
        if request.round_name:
            print(f"Round: {request.round_name}")
        print(f"Prompt:\n{request.prompt}\n")
        if request.transcript:
            print("Recent transcript:")
            for item in request.transcript[-4:]:
                speaker = item.metadata.get("speaker", item.role)
                print(f"- {speaker}: {item.content[:180]}")
            print()

        response = self._read_block("Paste reply. End with /done")
        notebook_append = self._read_optional_block("Optional notebook note. End with /done or /skip")
        state_patch = self._read_state_patch()
        return TurnResult(
            response_text=response,
            notebook_append=notebook_append,
            state_patch=state_patch,
            metadata={"adapter_type": "manual"},
        )

    def prepare_private_prep(self, prompt: str) -> str:
        print(f"\n[{self.definition.display_name} · private prep]")
        print(prompt)
        return self._read_optional_block("Optional private prep note. End with /done or /skip")

    @staticmethod
    def _read_block(label: str) -> str:
        print(label)
        lines: list[str] = []
        while True:
            line = input()
            if line.strip() == "/done":
                break
            lines.append(line)
        return "\n".join(lines).strip()

    @classmethod
    def _read_optional_block(cls, label: str) -> str:
        print(label)
        first = input()
        if first.strip() == "/skip":
            return ""
        lines = [] if first.strip() == "/done" else [first]
        while first.strip() != "/done":
            line = input()
            if line.strip() == "/done":
                break
            lines.append(line)
        return "\n".join(lines).strip()

    @staticmethod
    def _read_state_patch() -> dict:
        raw = input("Optional JSON state patch (blank to skip): ").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            print("State patch ignored: invalid JSON.")
            return {}
        if not isinstance(parsed, dict):
            print("State patch ignored: expected a JSON object.")
            return {}
        return parsed


def build_adapter(definition: AgentDefinition) -> AgentAdapter:
    if definition.adapter_type == "manual":
        return ManualAgentAdapter(definition)
    if definition.adapter_type == "anthropic":
        return AnthropicAgentAdapter(definition)
    raise ValueError(f"Unsupported adapter type `{definition.adapter_type}` for {definition.agent_id}.")


class AnthropicAgentAdapter(AgentAdapter):
    def __init__(self, definition: AgentDefinition):
        super().__init__(definition)
        self.model = definition.settings.get("model", "claude-opus-4-1-20250805")
        self.max_tokens = int(definition.settings.get("max_tokens", 1400))
        self.system_prompt_path = definition.definition_dir / definition.settings["system_prompt_file"]
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for Anthropic-backed adapters.")
        try:
            import anthropic
        except ModuleNotFoundError as exc:
            raise RuntimeError("The `anthropic` package is required for Anthropic-backed adapters.") from exc
        self.client = anthropic.Anthropic(api_key=api_key)

    def run_turn(self, request: TurnRequest) -> TurnResult:
        system_prompt = self.system_prompt_path.read_text(encoding="utf-8").strip()
        repo_root = self.definition.definition_dir.parents[1]
        corpus = load_shared_corpus(repo_root)
        transcript_text = self._format_transcript(request.transcript[-12:])
        prompt = self._build_user_prompt(request, corpus, transcript_text)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text")).strip()
        return TurnResult(
            response_text=text,
            metadata={"adapter_type": "anthropic", "model": self.model},
        )

    @staticmethod
    def _format_transcript(transcript) -> str:
        if not transcript:
            return "No prior transcript."
        lines: list[str] = []
        for item in transcript:
            speaker = item.metadata.get("speaker", item.role)
            lines.append(f"{speaker}: {item.content}")
        return "\n".join(lines)

    def _build_user_prompt(self, request: TurnRequest, corpus: str, transcript_text: str) -> str:
        notebook = request.notebook_text.strip() or "No notebook yet."
        state = json.dumps(request.state, indent=2, sort_keys=True) if request.state else "{}"
        corpus_block = corpus if corpus else "No shared corpus file loaded yet."
        return f"""Phase: {request.phase}
Conversation: {request.conversation_name}
Round: {request.round_name or "individual"}

Shared literature:
{corpus_block}

Private notebook:
{notebook}

Current state:
{state}

Recent transcript:
{transcript_text}

Current prompt:
{request.prompt}
""".strip()

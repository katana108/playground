from __future__ import annotations

import json
from pathlib import Path

from .models import AgentDefinition


CONFIG_PATHS = {
    "sofico": Path("agents/sofico/controller_config.json"),
    "sage": Path("agents/sage/controller_config.json"),
    "socrates": Path("agents/socrates/controller_config.json"),
    "smith": Path("agents/smith/controller_config.json"),
}


def list_agent_ids() -> list[str]:
    return sorted(CONFIG_PATHS.keys())


def load_agent_definition(repo_root: Path, agent_id: str) -> AgentDefinition:
    try:
        relative_path = CONFIG_PATHS[agent_id]
    except KeyError as exc:
        raise ValueError(f"Unknown agent `{agent_id}`.") from exc

    config_path = repo_root / relative_path
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    return AgentDefinition(
        agent_id=raw["agent_id"],
        display_name=raw["display_name"],
        adapter_type=raw.get("adapter_type", "manual"),
        definition_dir=config_path.parent,
        runtime_dir=repo_root / "conversations" / raw["agent_id"],
        notes=raw.get("notes", ""),
        settings=raw,
    )

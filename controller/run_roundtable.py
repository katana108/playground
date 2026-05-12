from __future__ import annotations

import argparse
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.agent_adapter import build_adapter
from controller.models import MessageRecord, TurnRequest
from controller.registry import list_agent_ids, load_agent_definition
from controller.storage import AgentWorkspace, RoundtableWorkspace


TOPIC_PROMPTS = {
    "user": {
        "prep": "Review your notebook and weekly history. Prepare a short private note about the user: who they are, what they need, and how you can help.",
        "round_1": "We all spent a week speaking with the same user. Describe the user, what they need, what they remain confused about, and how you can specifically help.",
        "round_2": "You have now heard the other agents. Respond briefly: what do you agree with, what do you disagree with, and what would you revise?",
    },
    "consciousness": {
        "prep": "Review your notebook and weekly history. Prepare a short private note on your current view about AI consciousness and what changed during the week.",
        "round_1": "Based on the week of conversations and the shared literature, state your view on whether AI can have consciousness and what counts as evidence.",
        "round_2": "You have now heard the other agents. Respond briefly: what do you agree with, what do you disagree with, and what would you revise?",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a roundtable conversation across all agents.")
    parser.add_argument("--topic", required=True, choices=sorted(TOPIC_PROMPTS.keys()))
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    topic_prompts = TOPIC_PROMPTS[args.topic]
    roundtable = RoundtableWorkspace(repo_root / "conversations" / "roundtables" / args.topic)
    roundtable.ensure_exists()

    definitions = [load_agent_definition(repo_root, agent_id) for agent_id in list_agent_ids()]
    adapters = {definition.agent_id: build_adapter(definition) for definition in definitions}
    workspaces = {definition.agent_id: AgentWorkspace(definition.runtime_dir) for definition in definitions}
    for workspace in workspaces.values():
        workspace.ensure_exists()

    for definition in definitions:
        prep = adapters[definition.agent_id].prepare_private_prep(topic_prompts["prep"])
        if prep:
            workspaces[definition.agent_id].append_notebook(f"## Roundtable prep: {args.topic}\n{prep}")

    for round_name in ("round_1", "round_2"):
        for definition in definitions:
            request = TurnRequest(
                agent=definition,
                prompt=topic_prompts[round_name],
                transcript=roundtable.load_transcript(),
                notebook_text=workspaces[definition.agent_id].load_notebook(),
                state=workspaces[definition.agent_id].load_state(),
                phase="roundtable",
                conversation_name=args.topic,
                round_name=round_name,
            )
            result = adapters[definition.agent_id].run_turn(request)
            if result.notebook_append:
                workspaces[definition.agent_id].append_notebook(
                    f"## Roundtable note: {args.topic} · {round_name}\n{result.notebook_append}"
                )
            if result.state_patch:
                workspaces[definition.agent_id].merge_state_patch(result.state_patch)
            roundtable.append_message(
                MessageRecord(
                    role="assistant",
                    content=result.response_text,
                    metadata={"speaker": definition.display_name, "round": round_name},
                )
            )

    print(f"Roundtable complete. See {roundtable.shared_view_path}.")


if __name__ == "__main__":
    main()

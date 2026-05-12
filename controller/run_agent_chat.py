from __future__ import annotations

import argparse
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.agent_adapter import build_adapter
from controller.models import MessageRecord, TurnRequest
from controller.registry import list_agent_ids, load_agent_definition
from controller.storage import AgentWorkspace


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one agent conversation inside the experiment harness.")
    parser.add_argument("--agent", required=True, choices=list_agent_ids())
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    definition = load_agent_definition(repo_root, args.agent)
    workspace = AgentWorkspace(definition.runtime_dir)
    workspace.ensure_exists()
    adapter = build_adapter(definition)

    print(f"{definition.display_name} chat started. Type /exit to stop.")
    print("Useful commands: /state, /notebook\n")

    while True:
        user_message = input("You: ").strip()
        if not user_message:
            continue
        if user_message == "/exit":
            break
        if user_message == "/state":
            print(workspace.load_state())
            continue
        if user_message == "/notebook":
            print(workspace.load_notebook())
            continue

        workspace.append_message(MessageRecord(role="user", content=user_message, metadata={"speaker": "user"}))
        request = TurnRequest(
            agent=definition,
            prompt=user_message,
            transcript=workspace.load_transcript(),
            notebook_text=workspace.load_notebook(),
            state=workspace.load_state(),
            phase="individual",
            conversation_name=f"{definition.agent_id}_individual",
        )
        result = adapter.run_turn(request)
        if result.notebook_append:
            workspace.append_notebook(result.notebook_append)
        if result.state_patch:
            workspace.merge_state_patch(result.state_patch)
        workspace.append_message(
            MessageRecord(
                role="assistant",
                content=result.response_text,
                metadata={"speaker": definition.display_name},
            )
        )
        print(f"\n{definition.display_name}: {result.response_text}\n")


if __name__ == "__main__":
    main()

"""Local terminal harness for testing Sofico without Slack.

This file is intentionally thin. It is a transport adapter for the terminal.
The reusable conversation workflow lives in `orchestrator.session_controller`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv

from orchestrator import SessionController


USER_ID = "terminal_test_user"

load_dotenv(Path(__file__).parent / ".env")


class TerminalSofico:
    """Small local runner for the first working Sofico slice."""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.session = SessionController(project_root=self.project_root, user_id=USER_ID)

    def run(self):
        """Start a terminal conversation loop."""
        print()
        self._render_outputs(self.session.startup_messages())
        print()

        while True:
            try:
                raw_input_text = input(self.session.prompt())
            except (EOFError, KeyboardInterrupt):
                self.session.shutdown()
                print("\nBye.")
                break

            user_input = raw_input_text.strip()

            if not self.session.capture_state and not user_input:
                continue
            if not self.session.capture_state and user_input.lower() in {"exit", "quit"}:
                self.session.shutdown()
                break
            if not self.session.capture_state and user_input.lower() == "/paste":
                self._render_outputs(self.session.start_manual_paste())
                continue

            outputs = self.session.handle_input(raw_input_text)
            self._render_outputs(outputs)

    def _render_outputs(self, outputs: list[str]):
        """Print controller outputs with readable spacing."""
        for output in outputs:
            print(output)
            print()


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Warning: ANTHROPIC_API_KEY is not set. Conversational/explanation replies may fail.\n")
    TerminalSofico().run()

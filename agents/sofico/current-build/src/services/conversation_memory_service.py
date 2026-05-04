"""
Conversation Memory Service
Manages three layers of memory for each learner:

1. In-session conversation buffer (in-memory, cleared on session end)
2. Post-session summaries (written to memory.yaml after each session)
3. Weekly learning reports (proactive, auto-generated after 7 days)

A "session" ends when:
- The user explicitly ends a study session ("end", "quit")
- 15 minutes pass with no messages (timeout check on each incoming message)
"""

import json
import logging
import os
import re
from datetime import datetime, date
from typing import Optional

import anthropic

from llm_utils import MODEL_DEFAULT, llm_text

logger = logging.getLogger(__name__)

SESSION_TIMEOUT_MINUTES = 15


class ConversationMemoryService:

    def __init__(self, data_service):
        self.data_service = data_service
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # In-memory per-user state (lost on restart, by design)
        self._buffers = {}        # user_id -> list[{role, content, timestamp}]
        self._session_start = {}  # user_id -> datetime
        self._last_activity = {}  # user_id -> datetime

    # ── Conversation buffer ───────────────────────────────────────────────────

    def _restore_if_needed(self, user_id: str):
        """Load saved conversation buffer from disk if not yet in memory."""
        if user_id not in self._buffers:
            try:
                saved = self.data_service.load_conversation(user_id)
                if saved:
                    self._buffers[user_id] = saved
                    self._last_activity[user_id] = datetime.now()
                    self._session_start.setdefault(user_id, datetime.now())
            except Exception as e:
                logger.warning(f"Could not restore conversation for {user_id}: {e}")

    def add_message(self, user_id: str, role: str, content: str):
        """Add a message to the buffer and persist to disk."""
        self._restore_if_needed(user_id)
        if user_id not in self._buffers:
            self._buffers[user_id] = []
            self._session_start[user_id] = datetime.now()

        self._buffers[user_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self._last_activity[user_id] = datetime.now()

        # Trim to last 50 messages
        if len(self._buffers[user_id]) > 50:
            self._buffers[user_id] = self._buffers[user_id][-50:]

        # Persist so history survives restarts and deploys
        try:
            self.data_service.save_conversation(user_id, self._buffers[user_id])
        except Exception as e:
            logger.warning(f"Could not persist conversation for {user_id}: {e}")

    def get_history(self, user_id: str) -> list:
        """Return conversation history in LLM messages format (no timestamps)."""
        self._restore_if_needed(user_id)
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self._buffers.get(user_id, [])
        ]

    def add_system_note(self, user_id: str, content: str):
        """Persist a short internal breadcrumb in the conversation buffer."""
        self.add_message(user_id, "assistant", f"[system-note] {content}")

    def check_timeout(self, user_id: str) -> bool:
        """
        If last activity was >15 minutes ago, end the session silently.
        Returns True if a session was timed out and ended.
        """
        if user_id not in self._last_activity:
            return False
        elapsed = (datetime.now() - self._last_activity[user_id]).total_seconds()
        if elapsed > SESSION_TIMEOUT_MINUTES * 60:
            logger.info(f"Session timed out for {user_id}, generating summary")
            self.end_session(user_id)
            return True
        return False

    def end_session(self, user_id: str):
        """
        End the session: generate a summary, save to memory.yaml.
        Keeps the last 30 messages for cross-session continuity — does NOT wipe the buffer.
        Called explicitly (study session end) or on timeout.
        """
        buffer = self._buffers.get(user_id, [])
        if len(buffer) >= 2:
            try:
                summary = self._generate_session_summary(user_id, buffer)
                if summary:
                    self._save_session_summary(user_id, summary)
                    logger.info(f"Session summary saved for {user_id}")
            except Exception as e:
                logger.error(f"Failed to save session summary for {user_id}: {e}")

        # Keep last 30 messages so the next session starts with context
        if user_id in self._buffers:
            self._buffers[user_id] = self._buffers[user_id][-30:]
            try:
                self.data_service.save_conversation(user_id, self._buffers[user_id])
            except Exception as e:
                logger.warning(f"Could not persist trimmed conversation for {user_id}: {e}")

        self._session_start.pop(user_id, None)
        self._last_activity.pop(user_id, None)

    # ── Weekly report ─────────────────────────────────────────────────────────

    def is_weekly_report_due(self, user_id: str) -> bool:
        """Return True if 7+ days have passed since the last weekly report."""
        memory = self.data_service.load_memory(user_id)
        weekly = memory.get("weekly_summaries", [])

        if not weekly:
            # Only generate if at least 2 sessions exist (enough data to be meaningful)
            return len(memory.get("session_history", [])) >= 2

        last_date_str = weekly[-1].get("generated_date", "")
        if not last_date_str:
            return True
        try:
            last_date = date.fromisoformat(last_date_str)
            return (date.today() - last_date).days >= 7
        except ValueError:
            return True

    def generate_and_save_weekly_report(self, user_id: str) -> Optional[str]:
        """
        Generate a weekly learning report. Saves to memory.yaml.
        Returns Slack-formatted report text, or None if not enough data.
        """
        memory = self.data_service.load_memory(user_id)
        sessions = memory.get("session_history", [])[-10:]
        psych = memory.get("psychological_profile", {})

        if not sessions:
            return None

        sessions_text = "\n\n".join([
            f"Date: {s.get('date', 'unknown')}\n"
            f"Topics: {', '.join(s.get('topics', []))}\n"
            f"Summary: {s.get('summary', '')}\n"
            f"Struggles: {', '.join(s.get('struggles', []))}\n"
            f"Strengths: {', '.join(s.get('strengths', []))}\n"
            f"Psychological note: {s.get('psychological_notes', '')}"
            for s in sessions
        ])

        prompt = f"""You are generating a weekly learning report for a student. Be warm, specific, and insightful — not clinical.

Recent session data:
{sessions_text}

Known psychological profile so far:
{json.dumps(psych, indent=2) if psych else "Not yet established"}

Write a weekly report covering:
1. *What was learned* — specific topics and key concepts
2. *Patterns of struggle* — specific, not generic
3. *Patterns of strength* — what they're doing well
4. *Psychological observations* — learning tendencies, resistance patterns, best strategies noticed
5. *One specific recommendation* for the coming week

Format for Slack (use *bold* for section headers). Start with:
📊 *Weekly Learning Report — {date.today().strftime("%B %d, %Y")}*

Max 350 words. Human and direct — not a performance review."""

        try:
            response = self.client.messages.create(
                model=MODEL_DEFAULT,
                max_tokens=700,
                messages=[{"role": "user", "content": prompt}]
            )
            report_text = llm_text(response)
        except Exception as e:
            logger.error(f"Failed to generate weekly report: {e}")
            return None

        # Update psychological profile based on all recent sessions
        psych_update = self._update_psychological_profile(sessions, psych)

        # Save to memory
        memory.setdefault("weekly_summaries", []).append({
            "generated_date": date.today().isoformat(),
            "report": report_text,
            "sessions_covered": len(sessions)
        })
        memory["weekly_summaries"] = memory["weekly_summaries"][-12:]  # ~3 months

        if psych_update:
            memory["psychological_profile"] = psych_update

        self.data_service.save_memory(user_id, memory)
        logger.info(f"Weekly report generated and saved for {user_id}")
        return report_text

    # ── Memory context for system prompt ──────────────────────────────────────

    def get_memory_context(self, user_id: str) -> str:
        """
        Return a formatted block to inject into the system prompt.
        Includes: psychological profile, last 3 sessions, latest weekly summary.
        """
        memory = self.data_service.load_memory(user_id)
        if not memory:
            return ""

        parts = []

        # Psychological profile
        psych = memory.get("psychological_profile", {})
        if psych:
            parts.append("## What You Know About This Learner")
            if psych.get("learning_style"):
                parts.append(f"- Learning style: {psych['learning_style']}")
            if psych.get("strengths"):
                parts.append(f"- Strengths: {', '.join(psych['strengths'][:4])}")
            if psych.get("growth_areas"):
                parts.append(f"- Growth areas: {', '.join(psych['growth_areas'][:4])}")
            if psych.get("resistance_patterns"):
                parts.append(f"- Watch for: {', '.join(psych['resistance_patterns'][:3])}")
            if psych.get("best_strategies"):
                parts.append(f"- What works: {', '.join(psych['best_strategies'][:3])}")

        # Last 3 session summaries
        sessions = memory.get("session_history", [])[-3:]
        if sessions:
            parts.append("\n## Recent Sessions")
            for s in reversed(sessions):
                struggles = ", ".join(s.get("struggles", [])) or "nothing noted"
                parts.append(
                    f"- {s.get('date', '')}: {s.get('summary', '')} "
                    f"(struggled with: {struggles})"
                )

        # Latest weekly summary (shortened)
        weekly = memory.get("weekly_summaries", [])
        if weekly:
            latest = weekly[-1]
            report = latest.get("report", "")
            if len(report) > 400:
                report = report[:400] + "..."
            parts.append(f"\n## Latest Weekly Summary ({latest.get('generated_date', '')})")
            parts.append(report)

        return "\n".join(parts)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _parse_json(self, text: str) -> dict:
        """Extract a JSON object from LLM response, tolerating markdown fences and minor syntax issues."""
        text = text.strip()
        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try to extract the first {...} block
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON: {text[:120]}")

    def _generate_session_summary(self, user_id: str, buffer: list) -> Optional[dict]:
        """Ask LLM to summarize the conversation and extract learning observations."""
        conversation_text = "\n".join([
            f"{m['role'].upper()}: {m['content'][:400]}"
            for m in buffer
            if m["content"].strip()
        ])

        if len(conversation_text) < 80:
            return None

        prompt = f"""Analyze this learning session and extract structured observations.

Conversation:
{conversation_text[:4000]}

Return raw JSON only (no markdown fences):
{{
  "topics": ["topics discussed"],
  "summary": "2-3 sentence summary of what happened",
  "struggles": ["specific things they found hard"],
  "strengths": ["specific things they did well"],
  "observations": ["specific behavioral or learning patterns noticed"],
  "psychological_notes": "1 sentence about learning style, resistance, or notable patterns"
}}

Be specific. Only include what actually happened in this session. If nothing notable, return empty lists."""

        try:
            response = self.client.messages.create(
                model=MODEL_DEFAULT,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            text = llm_text(response)
            data = self._parse_json(text)
            data["date"] = date.today().isoformat()
            return data
        except Exception as e:
            logger.warning(f"Could not generate session summary: {e}")
            return {
                "date": date.today().isoformat(),
                "topics": [],
                "summary": "Session occurred but summary could not be generated.",
                "struggles": [],
                "strengths": [],
                "observations": [],
                "psychological_notes": ""
            }

    def _save_session_summary(self, user_id: str, summary: dict):
        memory = self.data_service.load_memory(user_id)
        history = memory.get("session_history", [])
        history.append(summary)
        memory["session_history"] = history[-30:]  # Keep last 30 sessions

        # Update psychological profile from all recent sessions (not just weekly)
        recent = history[-5:]  # Use last 5 sessions for profile update
        current_psych = memory.get("psychological_profile", {})
        psych_update = self._update_psychological_profile(recent, current_psych)
        if psych_update:
            memory["psychological_profile"] = psych_update

        self.data_service.save_memory(user_id, memory)

    def _update_psychological_profile(self, sessions: list, current_profile: dict) -> Optional[dict]:
        """Synthesize a psychological learning profile from recent session observations."""
        all_observations = []
        all_struggles = []
        all_strengths = []
        all_psych_notes = []

        for s in sessions:
            all_observations.extend(s.get("observations", []))
            all_struggles.extend(s.get("struggles", []))
            all_strengths.extend(s.get("strengths", []))
            if s.get("psychological_notes"):
                all_psych_notes.append(s["psychological_notes"])

        if not any([all_observations, all_struggles, all_strengths]):
            return None

        prompt = f"""Build a concise psychological learning profile from these observations.

Observations across sessions: {all_observations}
Struggles: {all_struggles}
Strengths: {all_strengths}
Psychological notes: {all_psych_notes}
Current profile: {json.dumps(current_profile) if current_profile else "none yet"}

Return raw JSON only (no markdown):
{{
  "learning_style": "1-sentence description",
  "strengths": ["up to 5 specific strengths"],
  "growth_areas": ["up to 5 specific growth areas"],
  "resistance_patterns": ["up to 3 patterns of resistance or avoidance"],
  "best_strategies": ["up to 3 strategies that work well for this learner"]
}}"""

        try:
            response = self.client.messages.create(
                model=MODEL_DEFAULT,
                max_tokens=350,
                messages=[{"role": "user", "content": prompt}]
            )
            text = llm_text(response)
            return self._parse_json(text)
        except Exception as e:
            logger.warning(f"Could not update psychological profile: {e}")
            return None

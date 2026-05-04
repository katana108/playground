"""
Progress Handler
Shows learning progress and statistics
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ProgressHandler:
    """Handles progress and statistics requests"""

    def __init__(self, gitlab_service):
        self.gitlab = gitlab_service

    def handle(self, event, say):
        """Handle progress request"""
        user = event.get("user")

        try:
            stats = self.gitlab.get_user_stats(user)

            if not stats:
                say(
                    "No progress data yet! Start by:\n"
                    "1. Adding study documents to your learner repo\n"
                    "2. Running `quiz me` to start studying"
                )
                return

            # Format progress message
            msg = self._format_progress(stats)
            say(msg)

        except Exception as e:
            logger.error(f"Error getting progress: {e}", exc_info=True)
            say("Sorry, I couldn't load your progress right now. Please try again.")

    def _format_progress(self, stats: Dict[str, Any]) -> str:
        """Format progress stats as a message"""
        msg = "*Your Learning Progress*\n\n"

        # Overall stats
        msg += f"*Overall:*\n"
        msg += f"- Total questions: {stats.get('total_questions', 0)}\n"
        msg += f"- Questions mastered (>80%): {stats.get('mastered', 0)}\n"
        msg += f"- Average mastery: {stats.get('avg_mastery', 0):.0%}\n"
        msg += f"- Study sessions: {stats.get('total_sessions', 0)}\n\n"

        # Due questions
        due = stats.get('due_today', 0)
        if due > 0:
            msg += f" *{due} questions due for review today!*\n\n"

        # Topics breakdown
        topics = stats.get('topics', {})
        if topics:
            msg += "*By Topic:*\n"
            for topic, data in topics.items():
                mastery = data.get('mastery', 0)
                bar = self._mastery_bar(mastery)
                msg += f"- {topic}: {bar} {mastery:.0%}\n"
            msg += "\n"

        # Weak areas
        weak = stats.get('weak_areas', [])
        if weak:
            msg += "*Focus Areas (lowest mastery):*\n"
            for area in weak[:3]:
                msg += f"- {area['topic']}: {area['category']} ({area['mastery']:.0%})\n"

        return msg

    def _mastery_bar(self, mastery: float) -> str:
        """Create a visual mastery bar"""
        filled = int(mastery * 10)
        empty = 10 - filled
        return "█" * filled + "░" * empty

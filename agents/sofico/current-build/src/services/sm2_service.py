"""
SM2 Service
Implements the SM-2 spaced repetition algorithm (used by Anki)
"""

import logging
from datetime import date, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SM2Service:
    """SM-2 spaced repetition algorithm"""

    def __init__(self):
        self.min_easiness = 1.3
        self.default_easiness = 2.5

    def update_schedule(self, question: Dict[str, Any], grade: int) -> Dict[str, Any]:
        """
        Update question schedule based on grade (0-5)

        Grade meanings:
        0 - Complete blackout
        1 - Wrong, but recognized answer
        2 - Wrong, but answer seemed easy
        3 - Correct with difficulty
        4 - Correct after hesitation
        5 - Perfect recall

        Returns updated schedule data
        """
        # Handle None grade (grading failed)
        if grade is None:
            logger.warning("Grade is None - not updating schedule")
            return {
                "interval": question.get("interval", 1),
                "easiness": question.get("easiness", self.default_easiness),
                "reps": question.get("reps", 0),
                "last_reviewed": question.get("last_reviewed"),
                "next_review": question.get("next_review"),
                "mastery": question.get("mastery", 0.0),
                "grading_failed": True
            }

        # Get current values
        easiness = question.get("easiness", self.default_easiness)
        interval = question.get("interval", 1)
        reps = question.get("reps", 0)

        # Calculate new values
        if grade < 3:
            # Failed - reset
            new_interval = 1
            new_reps = 0
        else:
            # Passed
            if reps == 0:
                new_interval = 1
            elif reps == 1:
                new_interval = 6
            else:
                new_interval = round(interval * easiness)

            new_reps = reps + 1

        # Update easiness factor
        new_easiness = easiness + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
        new_easiness = max(self.min_easiness, new_easiness)

        # Calculate next review date
        today = date.today()
        next_review = today + timedelta(days=new_interval)

        # Calculate mastery (0.0 to 1.0)
        mastery = grade / 5.0

        return {
            "interval": new_interval,
            "easiness": round(new_easiness, 2),
            "reps": new_reps,
            "last_reviewed": today.isoformat(),
            "next_review": next_review.isoformat(),
            "mastery": mastery
        }

    def get_initial_schedule(self) -> Dict[str, Any]:
        """Get initial schedule for a new question"""
        return {
            "interval": 1,
            "easiness": self.default_easiness,
            "reps": 0,
            "last_reviewed": None,
            "next_review": None,
            "mastery": 0.0
        }

    def calculate_priority(self, question: Dict[str, Any]) -> float:
        """
        Calculate study priority for a question.
        Lower score = higher priority (should study first)
        """
        mastery = question.get("mastery", 0)
        last_reviewed = question.get("last_reviewed")

        # Prioritize low mastery
        priority = mastery

        # Also prioritize questions not reviewed recently
        if last_reviewed:
            days_since = (date.today() - date.fromisoformat(last_reviewed)).days
            # Reduce priority slightly for recently reviewed
            priority += min(0.2, days_since * 0.01)

        return priority

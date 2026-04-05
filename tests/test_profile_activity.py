import unittest
from datetime import date

from app.services.profile_score.repository.activity import (
    compute_current_streak_days,
)


class ProfileActivityTests(unittest.TestCase):
    def test_current_streak_counts_consecutive_days_until_today(self) -> None:
        streak = compute_current_streak_days(
            [
                date(2026, 4, 4),
                date(2026, 4, 3),
                date(2026, 4, 2),
                date(2026, 3, 30),
            ],
            today=date(2026, 4, 4),
        )

        self.assertEqual(streak, 3)

    def test_current_streak_stays_alive_when_latest_activity_was_yesterday(self) -> None:
        streak = compute_current_streak_days(
            [
                date(2026, 4, 3),
                date(2026, 4, 2),
                date(2026, 4, 1),
            ],
            today=date(2026, 4, 4),
        )

        self.assertEqual(streak, 3)

    def test_current_streak_resets_after_more_than_one_day_without_activity(self) -> None:
        streak = compute_current_streak_days(
            [
                date(2026, 4, 2),
                date(2026, 4, 1),
                date(2026, 3, 31),
            ],
            today=date(2026, 4, 4),
        )

        self.assertEqual(streak, 0)


if __name__ == '__main__':
    unittest.main()

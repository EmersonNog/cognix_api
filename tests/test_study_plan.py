import unittest
from unittest.mock import Mock, patch

from app.services.study_plan.progress import build_weekly_progress
from app.services.study_plan.service import (
    normalize_priority_disciplines,
    preview_study_plan,
)


class StudyPlanTests(unittest.TestCase):
    def test_priority_disciplines_are_unique_trimmed_and_limited(self) -> None:
        values = normalize_priority_disciplines(
            [
                '  Matematica  ',
                'Biologia',
                'matematica',
                '',
                'Historia',
                'Geografia',
                'Quimica',
            ]
        )

        self.assertEqual(
            values,
            ['Matematica', 'Biologia', 'Historia', 'Geografia'],
        )

    def test_weekly_progress_weights_constancy_more_heavily(self) -> None:
        progress = build_weekly_progress(
            study_days_per_week=5,
            minutes_per_day=60,
            weekly_questions_goal=100,
            focus_mode='constancia',
            active_days_this_week=4,
            completed_minutes_this_week=120,
            answered_questions_this_week=30,
        )

        self.assertEqual(progress['active_days_percent'], 80)
        self.assertEqual(progress['minutes_percent'], 40)
        self.assertEqual(progress['questions_percent'], 30)
        self.assertEqual(progress['weekly_completion_percent'], 58)

    def test_weekly_progress_weights_performance_more_heavily(self) -> None:
        progress = build_weekly_progress(
            study_days_per_week=5,
            minutes_per_day=60,
            weekly_questions_goal=100,
            focus_mode='desempenho',
            active_days_this_week=4,
            completed_minutes_this_week=120,
            answered_questions_this_week=30,
        )

        self.assertEqual(progress['weekly_completion_percent'], 43)

    @patch('app.services.study_plan.service.fetch_weekly_metrics')
    @patch('app.services.study_plan.service.fetch_study_plan_row')
    def test_preview_study_plan_uses_backend_progress_rule(
        self,
        fetch_row_mock,
        fetch_weekly_metrics_mock,
    ) -> None:
        fetch_row_mock.return_value = {
            'updated_at': None,
            'priority_disciplines_json': '["Matematica"]',
        }
        fetch_weekly_metrics_mock.return_value = {
            'week_start': __import__('datetime').date(2026, 4, 6),
            'week_end': __import__('datetime').date(2026, 4, 12),
            'active_days_this_week': 4,
            'completed_minutes_this_week': 120,
            'answered_questions_this_week': 30,
        }

        payload = preview_study_plan(
            Mock(),
            user_id=7,
            payload={
                'study_days_per_week': 5,
                'minutes_per_day': 60,
                'weekly_questions_goal': 100,
                'focus_mode': 'desempenho',
                'preferred_period': 'noite',
                'priority_disciplines': ['Matematica', 'Historia'],
            },
        )

        self.assertTrue(payload['configured'])
        self.assertEqual(payload['study_days_per_week'], 5)
        self.assertEqual(payload['weekly_questions_goal'], 100)
        self.assertEqual(payload['active_days_percent'], 80)
        self.assertEqual(payload['minutes_percent'], 40)
        self.assertEqual(payload['questions_percent'], 30)
        self.assertEqual(payload['weekly_completion_percent'], 43)
        self.assertEqual(
            payload['priority_disciplines'],
            ['Matematica', 'Historia'],
        )


if __name__ == '__main__':
    unittest.main()

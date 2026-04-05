import unittest

from app.services.study_plan.progress import build_weekly_progress
from app.services.study_plan.service import normalize_priority_disciplines


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


if __name__ == '__main__':
    unittest.main()

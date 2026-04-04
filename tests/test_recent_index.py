import unittest

from app.services.profile_score.scoring import (
    calculate_recent_index_data,
    calculate_score_components,
)


class RecentIndexTests(unittest.TestCase):
    def test_recent_index_starts_at_zero_without_recent_data(self) -> None:
        recent_index_data = calculate_recent_index_data(
            recent_attempt_outcomes=[],
            recent_active_days=0,
            recent_completed_sessions=0,
            latest_session_accuracy_percent=0.0,
        )

        self.assertFalse(recent_index_data['recent_index_ready'])
        self.assertEqual(recent_index_data['recent_index'], 0)
        self.assertEqual(recent_index_data['exact_recent_index'], 0.0)

    def test_latest_correct_answer_improves_recent_index(self) -> None:
        mostly_wrong = calculate_recent_index_data(
            recent_attempt_outcomes=[False, False, True, False, False],
            recent_active_days=2,
            recent_completed_sessions=1,
            latest_session_accuracy_percent=55.0,
        )
        latest_correct = calculate_recent_index_data(
            recent_attempt_outcomes=[True, False, True, False, False],
            recent_active_days=2,
            recent_completed_sessions=1,
            latest_session_accuracy_percent=55.0,
        )

        self.assertGreater(
            latest_correct['exact_recent_index'],
            mostly_wrong['exact_recent_index'],
        )

    def test_score_fields_stay_stable_while_recent_index_changes(self) -> None:
        base_kwargs = {
            'unique_questions_answered': 120,
            'question_bank_total': 1000,
            'disciplines_covered': 4,
            'total_completed_sessions': 5,
            'historical_accuracy_percent': 68.0,
            'recent_completed_sessions': 1,
            'recent_active_days': 4,
            'latest_session_accuracy_percent': 62.0,
            'inactivity_days': 0,
        }

        variant_a = calculate_score_components(
            recent_attempt_outcomes=[False, False, False, True, False],
            **base_kwargs,
        )
        variant_b = calculate_score_components(
            recent_attempt_outcomes=[True, False, False, True, False],
            **base_kwargs,
        )

        self.assertEqual(variant_a['score'], variant_b['score'])
        self.assertEqual(variant_a['exact_score'], variant_b['exact_score'])
        self.assertGreater(variant_b['exact_recent_index'], variant_a['exact_recent_index'])
        self.assertNotIn('momentum_score', variant_a)
        self.assertNotIn('exact_momentum_score', variant_a)
        self.assertNotIn('momentum_label', variant_a)


if __name__ == '__main__':
    unittest.main()

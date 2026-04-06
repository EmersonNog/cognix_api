import unittest

from app.services.recommendations.candidates import (
    CandidateSnapshot,
    build_subcategory_candidates,
    question_total_from_snapshot,
)


class RecommendationCandidatesTests(unittest.TestCase):
    def test_build_subcategory_candidates_filters_by_exact_raw_discipline_match(
        self,
    ) -> None:
        snapshot = CandidateSnapshot(
            question_rows=[
                {
                    'discipline': 'Matematica',
                    'subcategory': 'Funcoes',
                    'total_questions': 10,
                },
                {
                    'discipline': ' Matematica ',
                    'subcategory': 'Funcoes',
                    'total_questions': 5,
                },
            ],
            attempt_rows=[
                {
                    'discipline': 'Matematica',
                    'subcategory': 'Funcoes',
                    'total_attempts': 4,
                    'total_correct': 2,
                },
                {
                    'discipline': ' Matematica ',
                    'subcategory': 'Funcoes',
                    'total_attempts': 2,
                    'total_correct': 1,
                },
            ],
        )

        candidates = build_subcategory_candidates(snapshot, discipline='Matematica')

        self.assertEqual(
            candidates,
            [
                {
                    'discipline': 'Matematica',
                    'subcategory': 'Funcoes',
                    'total_questions': 10,
                    'total_attempts': 4,
                    'accuracy_percent': 50.0,
                }
            ],
        )

    def test_question_total_from_snapshot_uses_exact_raw_match(self) -> None:
        snapshot = CandidateSnapshot(
            question_rows=[
                {
                    'discipline': 'Matematica',
                    'subcategory': 'Funcoes',
                    'total_questions': 10,
                },
                {
                    'discipline': ' Matematica ',
                    'subcategory': 'Funcoes',
                    'total_questions': 5,
                },
            ],
            attempt_rows=[],
        )

        total = question_total_from_snapshot(
            snapshot,
            discipline='Matematica',
            subcategory='Funcoes',
        )

        self.assertEqual(total, 10)


if __name__ == '__main__':
    unittest.main()

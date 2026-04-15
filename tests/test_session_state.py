import unittest
from datetime import UTC, datetime

from app.services.session_state import (
    CURRENT_SESSION_STATE_VERSION,
    LEGACY_SESSION_STATE_VERSION,
    SessionStateValidationError,
    derive_session_snapshot_columns,
    normalize_session_state_for_storage,
    parse_session_state,
)


class SessionStateTests(unittest.TestCase):
    def test_normalize_in_progress_session_state_accepts_legacy_payload(self) -> None:
        payload = normalize_session_state_for_storage(
            {
                'discipline': '  Ciencias da Natureza e suas Tecnologias ',
                'subcategory': ' Biologia ',
                'currentIndex': 2,
                'questionIds': [147, 147, 43],
                'selections': {'147': 4},
                'lastSubmitted': {'147': 'd'},
                'isCorrect': {'147': 'null'},
                'correctOptionIndexByQuestionId': {'147': 3},
                'elapsedSeconds': 12,
                'paused': False,
                'totalAvailable': 252,
                'offset': 20,
                'showingAnswerFeedback': False,
                'feedbackQuestionId': None,
                'currentCorrectOptionIndex': None,
                'lastAnswerWasCorrect': None,
                'savedAt': 1_776_211_359_647,
            }
        )

        self.assertEqual(payload['stateVersion'], LEGACY_SESSION_STATE_VERSION)
        self.assertEqual(payload['discipline'], 'Ciencias da Natureza e suas Tecnologias')
        self.assertEqual(payload['subcategory'], 'Biologia')
        self.assertFalse(payload['completed'])
        self.assertEqual(payload['questionIds'], [147, 43])
        self.assertEqual(payload['isCorrect'], {'147': None})

    def test_normalize_completed_session_state_keeps_version_and_result(self) -> None:
        payload = normalize_session_state_for_storage(
            {
                'stateVersion': CURRENT_SESSION_STATE_VERSION,
                'discipline': 'Matematica e suas Tecnologias',
                'subcategory': 'Geometria',
                'completed': True,
                'savedAt': 1_776_211_359_647,
                'result': {
                    'totalQuestions': 20,
                    'answeredQuestions': 18,
                    'correctAnswers': 15,
                    'wrongAnswers': 3,
                    'elapsedSeconds': 540,
                },
            }
        )

        snapshot = derive_session_snapshot_columns(payload)

        self.assertEqual(payload['stateVersion'], CURRENT_SESSION_STATE_VERSION)
        self.assertTrue(payload['completed'])
        self.assertEqual(snapshot['answered_questions'], 18)
        self.assertEqual(snapshot['total_questions'], 20)
        self.assertEqual(snapshot['elapsed_seconds'], 540)
        self.assertEqual(
            snapshot['saved_at'],
            datetime.fromtimestamp(1_776_211_359_647 / 1000, tz=UTC),
        )

    def test_normalize_session_state_rejects_invalid_question_key(self) -> None:
        with self.assertRaises(SessionStateValidationError) as exc_info:
            normalize_session_state_for_storage(
                {
                    'stateVersion': CURRENT_SESSION_STATE_VERSION,
                    'discipline': 'Matematica e suas Tecnologias',
                    'subcategory': 'Funcoes',
                    'currentIndex': 0,
                    'questionIds': [12],
                    'selections': {'abc': 1},
                    'lastSubmitted': {},
                    'isCorrect': {},
                    'correctOptionIndexByQuestionId': {},
                    'elapsedSeconds': 1,
                    'paused': False,
                    'totalAvailable': 12,
                    'offset': 0,
                    'showingAnswerFeedback': False,
                    'feedbackQuestionId': None,
                    'currentCorrectOptionIndex': None,
                    'lastAnswerWasCorrect': None,
                    'savedAt': 1_776_211_359_647,
                }
            )

        self.assertIn('state.selections', str(exc_info.exception))

    def test_parse_session_state_returns_empty_dict_for_invalid_json(self) -> None:
        self.assertEqual(parse_session_state('{invalid'), {})


if __name__ == '__main__':
    unittest.main()

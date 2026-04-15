import json
import unittest
from datetime import UTC, datetime

from app.api.endpoints.sessions.helpers import (
    build_completed_history_overview_item,
    build_session_overview_item,
    resolve_session_saved_at,
    resolve_session_state_version,
)
from app.core.datetime_utils import to_api_iso


class SessionHelpersTests(unittest.TestCase):
    def test_build_session_overview_item_exposes_explicit_session_timestamp(self) -> None:
        saved_at = datetime(2026, 4, 15, 0, 2, 39, tzinfo=UTC)
        updated_at = datetime(2026, 4, 15, 0, 3, 15, tzinfo=UTC)
        row = {
            'discipline': 'Ciencias da Natureza e suas Tecnologias',
            'subcategory': 'Biologia',
            'state_version': 2,
            'completed': False,
            'answered_questions': 3,
            'total_questions': 20,
            'elapsed_seconds': 45,
            'saved_at': saved_at,
            'updated_at': updated_at,
        }

        item = build_session_overview_item(row)

        self.assertEqual(resolve_session_saved_at(row), saved_at)
        self.assertEqual(item['session_at'], to_api_iso(saved_at))
        self.assertEqual(item['saved_at'], to_api_iso(saved_at))
        self.assertEqual(item['updated_at'], to_api_iso(updated_at))

    def test_build_completed_history_overview_item_exposes_completed_at(self) -> None:
        completed_at = datetime(2026, 4, 15, 13, 50, 6, tzinfo=UTC)

        item = build_completed_history_overview_item(
            {
                'discipline': 'Linguagens, Codigos e suas Tecnologias',
                'subcategory': 'Educacao Fisica',
                'answered_questions': 17,
                'total_questions': 17,
                'completed_at': completed_at,
            }
        )

        self.assertEqual(item['session_at'], to_api_iso(completed_at))
        self.assertEqual(item['completed_at'], to_api_iso(completed_at))
        self.assertEqual(item['updated_at'], to_api_iso(completed_at))

    def test_resolve_session_metadata_falls_back_to_state_payload(self) -> None:
        saved_at = datetime.fromtimestamp(1_776_211_359_647 / 1000, tz=UTC)
        row = {
            'state_json': json.dumps(
                {
                    'stateVersion': 2,
                    'discipline': 'Ciencias da Natureza e suas Tecnologias',
                    'subcategory': 'Biologia',
                    'completed': False,
                    'currentIndex': 0,
                    'questionIds': [147, 43],
                    'selections': {'147': 4},
                    'lastSubmitted': {'147': 'D'},
                    'isCorrect': {'147': None},
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
            ),
            'updated_at': None,
        }

        self.assertEqual(resolve_session_state_version(row), 2)
        self.assertEqual(resolve_session_saved_at(row), saved_at)


if __name__ == '__main__':
    unittest.main()

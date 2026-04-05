from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.services.profile_score.repository.sessions import (
    build_recent_completed_session_item,
    fetch_recent_completed_session_items,
)
from app.services.profile_score.service.profile_payload import fetch_profile_score


def test_build_recent_completed_session_item_uses_answered_questions_for_accuracy() -> None:
    item = build_recent_completed_session_item(
        {
            'discipline': 'Matematica e suas Tecnologias',
            'subcategory': 'Geometria Espacial',
            'answered_questions': 18,
            'total_questions': 20,
            'correct_answers': 15,
            'completed_at': datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
        }
    )

    assert item is not None
    assert item['accuracy_percent'] == 83.3
    assert item['correct_answers'] == 15
    assert item['answered_questions'] == 18


def test_fetch_recent_completed_session_items_deduplicates_retries() -> None:
    class _FakeQuery:
        def where(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

    rows = [
        {
            'discipline': 'Linguagens, Codigos e suas Tecnologias',
            'subcategory': 'Gramatica',
            'answered_questions': 16,
            'total_questions': 16,
            'correct_answers': 3,
            'completed_at': datetime(2026, 4, 5, 13, 5, tzinfo=timezone.utc),
        },
        {
            'discipline': 'Matematica e suas Tecnologias',
            'subcategory': 'Raciocinio Logico',
            'answered_questions': 16,
            'total_questions': 16,
            'correct_answers': 4,
            'completed_at': datetime(2026, 4, 5, 13, 2, tzinfo=timezone.utc),
        },
        {
            'discipline': 'Linguagens, Codigos e suas Tecnologias',
            'subcategory': 'Gramatica',
            'answered_questions': 16,
            'total_questions': 16,
            'correct_answers': 8,
            'completed_at': datetime(2026, 4, 5, 12, 50, tzinfo=timezone.utc),
        },
        {
            'discipline': 'Ciencias Humanas e suas Tecnologias',
            'subcategory': 'Sociologia',
            'answered_questions': 12,
            'total_questions': 12,
            'correct_answers': 9,
            'completed_at': datetime(2026, 4, 5, 12, 45, tzinfo=timezone.utc),
        },
    ]
    db = Mock()
    db.execute.return_value.mappings.return_value.all.return_value = rows
    session_history = Mock()
    session_history.c.user_id = Mock()
    session_history.c.discipline = Mock()
    session_history.c.subcategory = Mock()
    session_history.c.correct_answers = Mock()
    session_history.c.answered_questions = Mock()
    session_history.c.total_questions = Mock()
    session_history.c.completed_at = Mock()
    session_history.c.id = Mock()

    with patch('app.services.profile_score.repository.sessions.select') as select_mock:
        select_mock.return_value = _FakeQuery()
        items = fetch_recent_completed_session_items(
            db,
            session_history,
            user_id=7,
            limit=3,
        )

    assert [item['subcategory'] for item in items] == [
        'Gramatica',
        'Raciocinio Logico',
        'Sociologia',
    ]
    assert items[0]['correct_answers'] == 3


@patch('app.services.profile_score.service.profile_payload.calculate_score_components')
@patch('app.services.profile_score.service.profile_payload.fetch_profile_metrics')
def test_fetch_profile_score_includes_recent_completed_sessions_preview(
    fetch_profile_metrics_mock,
    calculate_score_components_mock,
) -> None:
    preview_items = [
        {
            'discipline': 'Linguagens, Codigos e suas Tecnologias',
            'subcategory': 'Gramatica',
            'answered_questions': 20,
            'total_questions': 20,
            'correct_answers': 18,
            'accuracy_percent': 90.0,
            'completed_at': datetime(2026, 4, 5, 9, 30, tzinfo=timezone.utc),
        }
    ]
    fetch_profile_metrics_mock.return_value = {
        'last_activity_at': datetime(2026, 4, 5, 9, 30, tzinfo=timezone.utc),
        'unique_questions_answered': 120,
        'question_bank_total': 800,
        'disciplines_covered': 4,
        'completed_sessions': 7,
        'accuracy_percent': 71.2,
        'recent_completed_sessions': 2,
        'recent_active_days': 5,
        'recent_attempt_outcomes': [True, False, True],
        'total_questions': 150,
        'total_correct': 107,
        'total_study_seconds': 5400,
        'active_days_last_30': 11,
        'current_streak_days': 3,
        'recent_activity_window': [],
        'recent_completed_sessions_preview': preview_items,
        'question_rows': [],
        'strongest_subcategory': None,
        'weakest_subcategory': None,
        'attention_subcategories_count': 0,
        'latest_session_accuracy_percent': 90.0,
    }
    calculate_score_components_mock.return_value = {
        'score': 420,
        'exact_score': 420.0,
        'level': 'Avancado',
        'recent_index': 73,
        'exact_recent_index': 73.0,
        'recent_index_ready': True,
        'next_level': ('Elite', 80),
        'score_breakdown': {},
        'recent_index_breakdown': {},
    }

    payload = fetch_profile_score(Mock(), user_id=7)

    assert payload['recent_completed_sessions_preview'] == [
        {
            **preview_items[0],
            'completed_at': '2026-04-05T09:30:00+00:00',
        }
    ]

from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from app.services.profile_score.repository.profile_metrics import fetch_profile_metrics


@patch('app.services.profile_score.repository.profile_metrics.fetch_recent_completed_session_items')
@patch('app.services.profile_score.repository.profile_metrics.fetch_activity_dates')
@patch('app.services.profile_score.repository.profile_metrics.latest_session_accuracy_percent')
@patch('app.services.profile_score.repository.profile_metrics.recent_attempt_outcomes')
@patch('app.services.profile_score.repository.profile_metrics.build_subcategory_insights')
@patch('app.services.profile_score.repository.profile_metrics.get_sessions_table')
@patch('app.services.profile_score.repository.profile_metrics.get_session_history_table')
@patch('app.services.profile_score.repository.profile_metrics.get_questions_table')
@patch('app.services.profile_score.repository.profile_metrics.get_attempt_history_table')
@patch('app.services.profile_score.repository.profile_metrics.utc_now')
@patch('app.services.profile_score.repository.profile_metrics._fetch_session_history_aggregates')
@patch('app.services.profile_score.repository.profile_metrics._fetch_attempt_history_aggregates')
def test_fetch_profile_metrics_preserves_payload_shape_with_aggregated_queries(
    fetch_attempt_history_aggregates_mock,
    fetch_session_history_aggregates_mock,
    utc_now_mock,
    get_attempt_history_table_mock,
    get_questions_table_mock,
    get_session_history_table_mock,
    get_sessions_table_mock,
    build_subcategory_insights_mock,
    recent_attempt_outcomes_mock,
    latest_session_accuracy_percent_mock,
    fetch_activity_dates_mock,
    fetch_recent_completed_session_items_mock,
) -> None:
    now = datetime(2026, 4, 6, 15, 0, tzinfo=timezone.utc)
    utc_now_mock.return_value = now

    attempt_history = Mock()
    attempt_history.c.discipline = Mock()
    attempt_history.c.question_id = Mock()
    attempt_history.c.user_id = Mock()
    get_attempt_history_table_mock.return_value = attempt_history

    questions = Mock()
    get_questions_table_mock.return_value = questions

    session_history = Mock()
    get_session_history_table_mock.return_value = session_history

    sessions = Mock()
    get_sessions_table_mock.return_value = sessions

    fetch_attempt_history_aggregates_mock.return_value = {
        'total_questions': 150,
        'unique_questions_answered': 120,
        'total_correct': 107,
        'active_days_last_30': 11,
        'recent_active_days': 5,
        'last_attempt_at': datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc),
    }
    fetch_session_history_aggregates_mock.return_value = {
        'completed_sessions': 7,
        'total_study_seconds': 5400,
        'recent_completed_sessions': 2,
        'history_last_completed_session_at': datetime(
            2026,
            4,
            5,
            9,
            30,
            tzinfo=timezone.utc,
        ),
    }
    build_subcategory_insights_mock.return_value = (
        {'discipline': 'Matematica', 'subcategory': 'Geometria'},
        {'discipline': 'Fisica', 'subcategory': 'Dinamica'},
        3,
    )
    recent_attempt_outcomes_mock.return_value = [True, False, True]
    latest_session_accuracy_percent_mock.return_value = 90.0
    fetch_activity_dates_mock.return_value = [
        date(2026, 4, 5),
        date(2026, 4, 4),
        date(2026, 4, 3),
    ]
    preview_items = [
        {
            'discipline': 'Matematica',
            'subcategory': 'Geometria',
            'answered_questions': 18,
            'total_questions': 20,
            'correct_answers': 15,
            'accuracy_percent': 83.3,
            'completed_at': datetime(2026, 4, 5, 9, 30, tzinfo=timezone.utc),
        }
    ]
    fetch_recent_completed_session_items_mock.return_value = preview_items

    question_rows = [('Matematica', 80), ('Fisica', 70)]
    db = Mock()
    db.execute.side_effect = [
        Mock(scalar=Mock(return_value=800)),
        Mock(all=Mock(return_value=question_rows)),
    ]

    payload = fetch_profile_metrics(db, user_id=7)

    assert payload == {
        'total_questions': 150,
        'unique_questions_answered': 120,
        'question_bank_total': 800,
        'disciplines_covered': 2,
        'total_correct': 107,
        'accuracy_percent': 71.3,
        'active_days_last_30': 11,
        'completed_sessions': 7,
        'total_study_seconds': 5400,
        'last_activity_at': datetime(2026, 4, 5, 9, 30, tzinfo=timezone.utc),
        'current_streak_days': 3,
        'recent_activity_window': [
            {'date': '2026-03-31', 'active': False, 'is_today': False},
            {'date': '2026-04-01', 'active': False, 'is_today': False},
            {'date': '2026-04-02', 'active': False, 'is_today': False},
            {'date': '2026-04-03', 'active': True, 'is_today': False},
            {'date': '2026-04-04', 'active': True, 'is_today': False},
            {'date': '2026-04-05', 'active': True, 'is_today': False},
            {'date': '2026-04-06', 'active': False, 'is_today': True},
        ],
        'recent_completed_sessions_preview': preview_items,
        'question_rows': question_rows,
        'strongest_subcategory': {'discipline': 'Matematica', 'subcategory': 'Geometria'},
        'weakest_subcategory': {'discipline': 'Fisica', 'subcategory': 'Dinamica'},
        'attention_subcategories_count': 3,
        'recent_attempt_outcomes': [True, False, True],
        'recent_completed_sessions': 2,
        'recent_active_days': 5,
        'latest_session_accuracy_percent': 90.0,
    }

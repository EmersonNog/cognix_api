from sqlalchemy.orm import Session

from app.core.datetime_utils import to_api_iso, utc_now
from app.services.profile_score.constants import (
    CONSISTENCY_DAYS_WINDOW,
    SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD,
)
from app.services.profile_score.repository import fetch_profile_metrics
from app.services.profile_score.scoring import calculate_score_components



def _serialize_questions_by_discipline(question_rows) -> list[dict]:
    return [
        {
            'discipline': str(discipline or '').strip(),
            'count': int(count or 0),
        }
        for discipline, count in question_rows
        if str(discipline or '').strip()
    ]



def fetch_profile_score(db: Session, user_id: int) -> dict:
    metrics = fetch_profile_metrics(db, user_id)
    last_activity_at = metrics['last_activity_at']
    inactivity_days = (
        max((utc_now().date() - last_activity_at.date()).days, 0)
        if last_activity_at is not None
        else 0
    )

    score_data = calculate_score_components(
        unique_questions_answered=metrics['unique_questions_answered'],
        question_bank_total=metrics['question_bank_total'],
        disciplines_covered=metrics['disciplines_covered'],
        total_completed_sessions=metrics['completed_sessions'],
        historical_accuracy_percent=metrics['accuracy_percent'],
        recent_completed_sessions=metrics['recent_completed_sessions'],
        recent_active_days=metrics['recent_active_days'],
        recent_attempt_outcomes=metrics['recent_attempt_outcomes'],
        latest_session_accuracy_percent=metrics['latest_session_accuracy_percent'],
        inactivity_days=inactivity_days,
    )
    next_level, points_to_next_level = score_data['next_level']

    return {
        'score': score_data['score'],
        'exact_score': score_data['exact_score'],
        'level': score_data['level'],
        'recent_index': score_data['recent_index'],
        'exact_recent_index': score_data['exact_recent_index'],
        'recent_index_ready': score_data['recent_index_ready'],
        'questions_answered': metrics['total_questions'],
        'unique_questions_answered': metrics['unique_questions_answered'],
        'question_bank_total': metrics['question_bank_total'],
        'disciplines_covered': metrics['disciplines_covered'],
        'total_correct': metrics['total_correct'],
        'accuracy_percent': metrics['accuracy_percent'],
        'completed_sessions': metrics['completed_sessions'],
        'total_study_seconds': metrics['total_study_seconds'],
        'active_days_last_30': metrics['active_days_last_30'],
        'consistency_window_days': CONSISTENCY_DAYS_WINDOW,
        'last_activity_at': to_api_iso(metrics['last_activity_at']),
        'next_level': next_level,
        'points_to_next_level': points_to_next_level,
        'questions_by_discipline': _serialize_questions_by_discipline(
            metrics['question_rows']
        ),
        'strongest_subcategory': metrics['strongest_subcategory'],
        'weakest_subcategory': metrics['weakest_subcategory'],
        'attention_subcategories_count': metrics['attention_subcategories_count'],
        'attention_accuracy_threshold': SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD,
        'score_breakdown': score_data['score_breakdown'],
        'recent_index_breakdown': score_data['recent_index_breakdown'],
    }

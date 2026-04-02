from sqlalchemy.orm import Session

from app.core.datetime_utils import to_api_iso
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
    score_data = calculate_score_components(
        total_questions=metrics['total_questions'],
        accuracy_percent=metrics['accuracy_percent'],
        completed_sessions=metrics['completed_sessions'],
        active_days_last_30=metrics['active_days_last_30'],
    )
    next_level, points_to_next_level = score_data['next_level']

    return {
        'score': score_data['score'],
        'exact_score': score_data['exact_score'],
        'level': score_data['level'],
        'questions_answered': metrics['total_questions'],
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
    }

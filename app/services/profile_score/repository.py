import json
from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models import get_attempts_table, get_sessions_table
from app.services.profile_score.constants import (
    CONSISTENCY_DAYS_WINDOW,
    SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD,
    SUBCATEGORY_INSIGHT_MIN_ATTEMPTS,
)


def _parse_completed_state(state_json: str | None) -> bool:
    try:
        payload = json.loads(state_json or '{}')
    except json.JSONDecodeError:
        return False
    return payload.get('completed') is True


def _parse_elapsed_seconds(state_json: str | None) -> int:
    try:
        payload = json.loads(state_json or '{}')
    except json.JSONDecodeError:
        return 0

    if payload.get('completed') is True:
        result = payload.get('result')
        if isinstance(result, dict):
            return int(result.get('elapsedSeconds') or 0)

    return int(payload.get('elapsedSeconds') or 0)


def _build_subcategory_insights(
    db: Session,
    attempts,
    user_id: int,
) -> tuple[dict | None, dict | None, int]:
    rows = db.execute(
        select(
            attempts.c.discipline,
            attempts.c.subcategory,
            func.count().label('total_attempts'),
            func.sum(case((attempts.c.is_correct.is_(True), 1), else_=0)).label(
                'total_correct'
            ),
        )
        .where(attempts.c.user_id == user_id)
        .where(attempts.c.discipline.is_not(None))
        .where(attempts.c.subcategory.is_not(None))
        .group_by(attempts.c.discipline, attempts.c.subcategory)
    ).all()

    stats = []
    for discipline, subcategory, total_attempts, total_correct in rows:
        normalized_discipline = str(discipline or '').strip()
        normalized_subcategory = str(subcategory or '').strip()
        attempts_count = int(total_attempts or 0)
        correct_count = int(total_correct or 0)

        if not normalized_discipline or not normalized_subcategory or attempts_count <= 0:
            continue

        accuracy_percent = round((correct_count / attempts_count) * 100, 1)
        stats.append(
            {
                'discipline': normalized_discipline,
                'subcategory': normalized_subcategory,
                'accuracy_percent': accuracy_percent,
                'total_attempts': attempts_count,
                'total_correct': correct_count,
            }
        )

    if not stats:
        return None, None, 0

    pedagogical_base = [
        item
        for item in stats
        if item['total_attempts'] >= SUBCATEGORY_INSIGHT_MIN_ATTEMPTS
    ]
    ranked = pedagogical_base or stats

    strongest = max(
        ranked,
        key=lambda item: (item['accuracy_percent'], item['total_attempts']),
    )
    weakest = min(
        ranked,
        key=lambda item: (item['accuracy_percent'], -item['total_attempts']),
    )
    attention_subcategories_count = sum(
        1
        for item in ranked
        if item['accuracy_percent'] < SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD
    )
    return strongest, weakest, attention_subcategories_count


def fetch_profile_metrics(db: Session, user_id: int) -> dict:
    attempts = get_attempts_table(settings.attempts_table)
    sessions = get_sessions_table(settings.sessions_table)
    attempt_filters = attempts.c.user_id == user_id

    total_questions = int(
        db.execute(
            select(func.count()).select_from(attempts).where(attempt_filters)
        ).scalar()
        or 0
    )
    total_correct = int(
        db.execute(
            select(func.count())
            .select_from(attempts)
            .where(attempt_filters & attempts.c.is_correct.is_(True))
        ).scalar()
        or 0
    )
    accuracy_percent = (
        round((total_correct / total_questions) * 100, 1) if total_questions else 0.0
    )

    consistency_cutoff = utc_now() - timedelta(days=CONSISTENCY_DAYS_WINDOW - 1)
    active_days_last_30 = int(
        db.execute(
            select(func.count(func.distinct(func.date(attempts.c.answered_at))))
            .select_from(attempts)
            .where(attempt_filters)
            .where(attempts.c.answered_at >= consistency_cutoff)
        ).scalar()
        or 0
    )

    completed_rows = db.execute(
        select(sessions.c.state_json).where(sessions.c.user_id == user_id)
    ).all()
    completed_sessions = sum(1 for row in completed_rows if _parse_completed_state(row[0]))
    total_study_seconds = sum(_parse_elapsed_seconds(row[0]) for row in completed_rows)

    last_activity_at = db.execute(
        select(func.max(attempts.c.answered_at))
        .select_from(attempts)
        .where(attempt_filters)
    ).scalar()

    question_rows = db.execute(
        select(
            attempts.c.discipline,
            func.count().label('count'),
        )
        .where(attempt_filters)
        .where(attempts.c.discipline.is_not(None))
        .group_by(attempts.c.discipline)
        .order_by(func.count().desc())
    ).all()

    strongest_subcategory, weakest_subcategory, attention_subcategories_count = (
        _build_subcategory_insights(db, attempts, user_id)
    )

    return {
        'total_questions': total_questions,
        'total_correct': total_correct,
        'accuracy_percent': accuracy_percent,
        'active_days_last_30': active_days_last_30,
        'completed_sessions': completed_sessions,
        'total_study_seconds': total_study_seconds,
        'last_activity_at': last_activity_at,
        'question_rows': question_rows,
        'strongest_subcategory': strongest_subcategory,
        'weakest_subcategory': weakest_subcategory,
        'attention_subcategories_count': attention_subcategories_count,
    }

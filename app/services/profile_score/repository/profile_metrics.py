from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models import (
    get_attempt_history_table,
    get_questions_table,
    get_session_history_table,
    get_sessions_table,
)
from app.db.session import engine
from ..constants import (
    CONSISTENCY_DAYS_WINDOW,
    SCORE_CONSISTENCY_WINDOW_DAYS,
    SCORE_RECENT_ACCURACY_WINDOW_DAYS,
    SCORE_SIMULATION_WINDOW_DAYS,
)

from .activity import (
    build_recent_activity_window,
    compute_current_streak_days,
    count_active_days,
    fetch_activity_dates,
    latest_timestamp,
    recent_attempt_outcomes,
)
from .insights import build_subcategory_insights
from .sessions import (
    fallback_completed_session_metrics,
    fetch_recent_completed_session_items,
    latest_session_accuracy_percent,
)


def fetch_profile_metrics(db: Session, user_id: int) -> dict:
    now = utc_now()
    attempt_history = get_attempt_history_table(settings.attempt_history_table)
    questions = get_questions_table(engine, settings.question_table)
    session_history = get_session_history_table(settings.session_history_table)
    sessions = get_sessions_table(settings.sessions_table)

    total_questions = int(
        db.execute(
            select(func.count())
            .select_from(attempt_history)
            .where(attempt_history.c.user_id == user_id)
        ).scalar()
        or 0
    )
    unique_questions_answered = int(
        db.execute(
            select(func.count(func.distinct(attempt_history.c.question_id)))
            .select_from(attempt_history)
            .where(attempt_history.c.user_id == user_id)
        ).scalar()
        or 0
    )
    question_bank_total = int(
        db.execute(select(func.count()).select_from(questions)).scalar()
        or 0
    )

    total_correct = int(
        db.execute(
            select(func.count())
            .select_from(attempt_history)
            .where(attempt_history.c.user_id == user_id)
            .where(attempt_history.c.is_correct.is_(True))
        ).scalar()
        or 0
    )
    accuracy_percent = (
        round((total_correct / total_questions) * 100, 1) if total_questions else 0.0
    )

    consistency_cutoff = now - timedelta(days=CONSISTENCY_DAYS_WINDOW - 1)
    active_days_last_30 = count_active_days(
        db,
        attempt_history,
        user_id,
        consistency_cutoff,
    )

    question_rows = db.execute(
        select(
            attempt_history.c.discipline,
            func.count().label('count'),
        )
        .where(attempt_history.c.user_id == user_id)
        .where(attempt_history.c.discipline.is_not(None))
        .group_by(attempt_history.c.discipline)
        .order_by(func.count().desc())
    ).all()

    disciplines_covered = len(question_rows)

    strongest_subcategory, weakest_subcategory, attention_subcategories_count = (
        build_subcategory_insights(db, attempt_history, user_id)
    )

    recent_accuracy_cutoff = now - timedelta(days=SCORE_RECENT_ACCURACY_WINDOW_DAYS - 1)
    recent_attempts = recent_attempt_outcomes(
        db,
        attempt_history,
        user_id,
        recent_accuracy_cutoff,
    )

    recent_consistency_cutoff = now - timedelta(days=SCORE_CONSISTENCY_WINDOW_DAYS - 1)
    recent_active_days = count_active_days(
        db,
        attempt_history,
        user_id,
        recent_consistency_cutoff,
    )

    recent_sessions_cutoff = now - timedelta(days=SCORE_SIMULATION_WINDOW_DAYS - 1)
    completed_sessions = int(
        db.execute(
            select(func.count())
            .select_from(session_history)
            .where(session_history.c.user_id == user_id)
        ).scalar()
        or 0
    )
    total_study_seconds = int(
        db.execute(
            select(func.coalesce(func.sum(session_history.c.elapsed_seconds), 0))
            .select_from(session_history)
            .where(session_history.c.user_id == user_id)
        ).scalar()
        or 0
    )
    recent_completed_sessions = int(
        db.execute(
            select(func.count())
            .select_from(session_history)
            .where(session_history.c.user_id == user_id)
            .where(session_history.c.completed_at >= recent_sessions_cutoff)
        ).scalar()
        or 0
    )
    history_last_completed_session_at = db.execute(
        select(func.max(session_history.c.completed_at))
        .select_from(session_history)
        .where(session_history.c.user_id == user_id)
    ).scalar()

    if completed_sessions == 0 and total_study_seconds == 0:
        fallback_metrics = fallback_completed_session_metrics(
            db,
            sessions,
            user_id,
            recent_sessions_cutoff,
        )
        completed_sessions = fallback_metrics['completed_sessions']
        total_study_seconds = fallback_metrics['total_study_seconds']
        recent_completed_sessions = fallback_metrics['recent_completed_sessions']

    latest_session_accuracy = latest_session_accuracy_percent(
        db,
        session_history,
        user_id,
    )

    last_activity_at = latest_timestamp(
        db.execute(
            select(func.max(attempt_history.c.answered_at))
            .select_from(attempt_history)
            .where(attempt_history.c.user_id == user_id)
        ).scalar(),
        history_last_completed_session_at,
    )
    activity_dates = fetch_activity_dates(
        db,
        attempt_history,
        session_history,
        user_id,
    )

    current_streak_days = compute_current_streak_days(
        activity_dates,
        today=now.date(),
    )
    recent_activity_window = build_recent_activity_window(
        activity_dates,
        today=now.date(),
    )
    recent_completed_sessions_preview = fetch_recent_completed_session_items(
        db,
        session_history,
        user_id,
    )

    return {
        'total_questions': total_questions,
        'unique_questions_answered': unique_questions_answered,
        'question_bank_total': question_bank_total,
        'disciplines_covered': disciplines_covered,
        'total_correct': total_correct,
        'accuracy_percent': accuracy_percent,
        'active_days_last_30': active_days_last_30,
        'completed_sessions': completed_sessions,
        'total_study_seconds': total_study_seconds,
        'last_activity_at': last_activity_at,
        'current_streak_days': current_streak_days,
        'recent_activity_window': recent_activity_window,
        'recent_completed_sessions_preview': recent_completed_sessions_preview,
        'question_rows': question_rows,
        'strongest_subcategory': strongest_subcategory,
        'weakest_subcategory': weakest_subcategory,
        'attention_subcategories_count': attention_subcategories_count,
        'recent_attempt_outcomes': recent_attempts,
        'recent_completed_sessions': recent_completed_sessions,
        'recent_active_days': recent_active_days,
        'latest_session_accuracy_percent': latest_session_accuracy,
    }

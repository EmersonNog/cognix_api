from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import get_attempt_history_table, get_session_history_table

from .constants import FOCUS_PROGRESS_WEIGHTS

def week_bounds(today: date) -> tuple[date, date]:
    week_start = today - timedelta(days=today.weekday())
    return week_start, week_start + timedelta(days=6)

def build_weekly_progress(
    *,
    study_days_per_week: int,
    minutes_per_day: int,
    weekly_questions_goal: int,
    focus_mode: str,
    active_days_this_week: int,
    completed_minutes_this_week: int,
    answered_questions_this_week: int,
) -> dict[str, int]:
    active_days_goal = max(study_days_per_week, 1)
    weekly_minutes_target = max(study_days_per_week * minutes_per_day, 1)
    questions_goal = max(weekly_questions_goal, 1)

    active_days_percent = min(
        round((active_days_this_week / active_days_goal) * 100),
        100,
    )
    minutes_percent = min(
        round((completed_minutes_this_week / weekly_minutes_target) * 100),
        100,
    )
    questions_percent = min(
        round((answered_questions_this_week / questions_goal) * 100),
        100,
    )

    weights = FOCUS_PROGRESS_WEIGHTS.get(focus_mode) or FOCUS_PROGRESS_WEIGHTS[
        'constancia'
    ]
    weekly_completion_percent = round(
        active_days_percent * weights['days']
        + minutes_percent * weights['minutes']
        + questions_percent * weights['questions']
    )

    return {
        'weekly_completion_percent': weekly_completion_percent,
        'active_days_goal': active_days_goal,
        'active_days_percent': active_days_percent,
        'weekly_minutes_target': weekly_minutes_target,
        'minutes_percent': minutes_percent,
        'questions_percent': questions_percent,
    }

def fetch_weekly_metrics(
    db: Session,
    *,
    user_id: int,
    today: date | None = None,
) -> dict[str, object]:
    current_day = today or datetime.now(timezone.utc).date()
    week_start, week_end = week_bounds(current_day)
    week_start_at = datetime.combine(week_start, time.min, tzinfo=timezone.utc)

    attempt_history = get_attempt_history_table(settings.attempt_history_table)
    session_history = get_session_history_table(settings.session_history_table)

    answered_questions_this_week = int(
        db.execute(
            select(func.count())
            .select_from(attempt_history)
            .where(attempt_history.c.user_id == user_id)
            .where(attempt_history.c.answered_at >= week_start_at)
        ).scalar()
        or 0
    )

    elapsed_seconds = int(
        db.execute(
            select(func.coalesce(func.sum(session_history.c.elapsed_seconds), 0))
            .select_from(session_history)
            .where(session_history.c.user_id == user_id)
            .where(session_history.c.completed_at >= week_start_at)
        ).scalar()
        or 0
    )
    completed_minutes_this_week = int(round(elapsed_seconds / 60)) if elapsed_seconds else 0

    attempt_dates = {
        answered_at.date()
        for (answered_at,) in db.execute(
            select(attempt_history.c.answered_at)
            .where(attempt_history.c.user_id == user_id)
            .where(attempt_history.c.answered_at >= week_start_at)
        ).all()
        if answered_at is not None
    }
    session_dates = {
        completed_at.date()
        for (completed_at,) in db.execute(
            select(session_history.c.completed_at)
            .where(session_history.c.user_id == user_id)
            .where(session_history.c.completed_at >= week_start_at)
        ).all()
        if completed_at is not None
    }
    active_days_this_week = len(attempt_dates | session_dates)

    return {
        'week_start': week_start,
        'week_end': week_end,
        'active_days_this_week': active_days_this_week,
        'completed_minutes_this_week': completed_minutes_this_week,
        'answered_questions_this_week': answered_questions_this_week,
    }

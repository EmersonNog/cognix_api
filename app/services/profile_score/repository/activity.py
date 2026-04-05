from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import RECENT_INDEX_ATTEMPT_SAMPLE_SIZE


def count_active_days(
    db: Session,
    attempt_history,
    user_id: int,
    cutoff,
) -> int:
    return int(
        db.execute(
            select(func.count(func.distinct(func.date(attempt_history.c.answered_at))))
            .select_from(attempt_history)
            .where(attempt_history.c.user_id == user_id)
            .where(attempt_history.c.answered_at >= cutoff)
        ).scalar()
        or 0
    )


def fetch_activity_dates(
    db: Session,
    attempt_history,
    session_history,
    user_id: int,
) -> list[date]:
    attempt_dates = _fetch_distinct_calendar_dates(
        db,
        attempt_history.c.answered_at,
        attempt_history.c.user_id,
        user_id,
    )
    session_dates = _fetch_distinct_calendar_dates(
        db,
        session_history.c.completed_at,
        session_history.c.user_id,
        user_id,
    )

    return sorted({*attempt_dates, *session_dates}, reverse=True)


def compute_current_streak_days(
    activity_dates: list[date],
    *,
    today: date,
) -> int:
    unique_dates = sorted(set(activity_dates), reverse=True)
    if not unique_dates:
        return 0

    latest_activity = unique_dates[0]
    if latest_activity < today - timedelta(days=1):
        return 0

    streak = 1
    previous_day = latest_activity

    for current_day in unique_dates[1:]:
        expected_previous = previous_day - timedelta(days=1)
        if current_day == expected_previous:
            streak += 1
            previous_day = current_day
            continue

        if current_day < expected_previous:
            break

    return streak


def build_recent_activity_window(
    activity_dates: list[date],
    *,
    today: date,
    window_days: int = 7,
) -> list[dict[str, object]]:
    unique_dates = set(activity_dates)
    start_day = today - timedelta(days=max(window_days - 1, 0))

    return [
        {
            'date': current_day.isoformat(),
            'active': current_day in unique_dates,
            'is_today': current_day == today,
        }
        for current_day in (
            start_day + timedelta(days=offset) for offset in range(window_days)
        )
    ]


def recent_attempt_outcomes(
    db: Session,
    attempt_history,
    user_id: int,
    cutoff,
) -> list[bool]:
    rows = db.execute(
        select(attempt_history.c.is_correct)
        .where(attempt_history.c.user_id == user_id)
        .where(attempt_history.c.answered_at >= cutoff)
        .where(attempt_history.c.is_correct.is_not(None))
        .order_by(attempt_history.c.answered_at.desc(), attempt_history.c.id.desc())
        .limit(RECENT_INDEX_ATTEMPT_SAMPLE_SIZE)
    ).all()

    return [bool(is_correct) for (is_correct,) in rows]


def latest_timestamp(*values):
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return max(valid)


def _fetch_distinct_calendar_dates(
    db: Session,
    timestamp_column,
    user_column,
    user_id: int,
) -> list[date]:
    rows = db.execute(
        select(func.date(timestamp_column))
        .where(user_column == user_id)
        .where(timestamp_column.is_not(None))
        .distinct()
    ).all()

    dates: list[date] = []
    for (raw_value,) in rows:
        coerced = _coerce_calendar_date(raw_value)
        if coerced is not None:
            dates.append(coerced)

    return dates


def _coerce_calendar_date(raw_value: object) -> date | None:
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    if isinstance(raw_value, str):
        try:
            return date.fromisoformat(raw_value)
        except ValueError:
            return None
    return None

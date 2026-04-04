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

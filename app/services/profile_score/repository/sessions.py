import json
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session


def parse_state(state_json: str | None) -> dict:
    try:
        return json.loads(state_json or '{}')
    except json.JSONDecodeError:
        return {}


def coerce_non_negative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def session_accuracy_percent(
    answered_questions: int,
    total_questions: int,
    correct_answers: int,
) -> float:
    denominator = answered_questions if answered_questions > 0 else total_questions
    if denominator <= 0:
        return 0.0
    return round((correct_answers / denominator) * 100, 1)


def fallback_completed_session_metrics(
    db: Session,
    sessions,
    user_id: int,
    recent_cutoff,
) -> dict:
    rows = db.execute(
        select(sessions.c.state_json, sessions.c.updated_at)
        .where(sessions.c.user_id == user_id)
        .order_by(sessions.c.updated_at.desc())
    ).all()

    completed_sessions = 0
    total_study_seconds = 0
    recent_completed_sessions = 0
    last_completed_at = None

    for state_json, updated_at in rows:
        payload = parse_state(state_json)
        if payload.get('completed') is not True:
            continue

        completed_sessions += 1
        if updated_at is not None and (
            last_completed_at is None or updated_at > last_completed_at
        ):
            last_completed_at = updated_at
        if updated_at is not None and updated_at >= recent_cutoff:
            recent_completed_sessions += 1

        result = payload.get('result') if isinstance(payload.get('result'), dict) else {}
        total_study_seconds += coerce_non_negative_int(
            result.get('elapsedSeconds') or payload.get('elapsedSeconds')
        )

    return {
        'completed_sessions': completed_sessions,
        'total_study_seconds': total_study_seconds,
        'recent_completed_sessions': recent_completed_sessions,
        'last_completed_at': last_completed_at,
    }


def fallback_completed_session_dates(
    db: Session,
    sessions,
    user_id: int,
) -> list[date]:
    rows = db.execute(
        select(sessions.c.state_json, sessions.c.updated_at)
        .where(sessions.c.user_id == user_id)
        .order_by(sessions.c.updated_at.desc())
    ).all()

    dates: set[date] = set()
    for state_json, updated_at in rows:
        payload = parse_state(state_json)
        if payload.get('completed') is not True:
            continue

        coerced = _coerce_calendar_date(updated_at)
        if coerced is not None:
            dates.add(coerced)

    return sorted(dates, reverse=True)


def latest_session_accuracy_percent(
    db: Session,
    session_history,
    user_id: int,
) -> float:
    rows = db.execute(
        select(
            session_history.c.correct_answers,
            session_history.c.answered_questions,
            session_history.c.total_questions,
        )
        .where(session_history.c.user_id == user_id)
        .order_by(session_history.c.completed_at.desc(), session_history.c.id.desc())
        .limit(1)
    ).all()

    if not rows:
        return 0.0

    latest_correct, latest_answered, latest_total = rows[0]
    return session_accuracy_percent(
        int(latest_answered or 0),
        int(latest_total or 0),
        int(latest_correct or 0),
    )


def _coerce_calendar_date(raw_value: object) -> date | None:
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    return None

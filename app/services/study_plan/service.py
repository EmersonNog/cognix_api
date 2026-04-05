from app.core.datetime_utils import to_api_iso

from .constants import (
    ALLOWED_FOCUS_MODES,
    ALLOWED_PREFERRED_PERIODS,
    DEFAULT_FOCUS_MODE,
    DEFAULT_MINUTES_PER_DAY,
    DEFAULT_PREFERRED_PERIOD,
    DEFAULT_STUDY_DAYS_PER_WEEK,
    DEFAULT_WEEKLY_QUESTIONS_GOAL,
    MAX_PRIORITY_DISCIPLINES,
)
from .progress import build_weekly_progress, fetch_weekly_metrics
from .repository import (
    fetch_study_plan_row,
    parse_priority_disciplines,
    upsert_study_plan_row,
)


def _normalize_int(raw: object, *, minimum: int, maximum: int, fallback: int) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return fallback
    return min(max(value, minimum), maximum)


def normalize_priority_disciplines(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []

    values: list[str] = []
    seen: set[str] = set()
    for item in raw:
        value = str(item or '').strip()
        if not value:
            continue
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        values.append(value)
        if len(values) >= MAX_PRIORITY_DISCIPLINES:
            break
    return values


def _normalize_focus_mode(raw: object) -> str:
    value = str(raw or '').strip().casefold()
    if value in ALLOWED_FOCUS_MODES:
        return value
    return DEFAULT_FOCUS_MODE


def _normalize_preferred_period(raw: object) -> str:
    value = str(raw or '').strip().casefold()
    if value in ALLOWED_PREFERRED_PERIODS:
        return value
    return DEFAULT_PREFERRED_PERIOD


def _normalize_study_plan_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        'study_days_per_week': _normalize_int(
            payload.get('study_days_per_week'),
            minimum=1,
            maximum=7,
            fallback=DEFAULT_STUDY_DAYS_PER_WEEK,
        ),
        'minutes_per_day': _normalize_int(
            payload.get('minutes_per_day'),
            minimum=15,
            maximum=240,
            fallback=DEFAULT_MINUTES_PER_DAY,
        ),
        'weekly_questions_goal': _normalize_int(
            payload.get('weekly_questions_goal'),
            minimum=10,
            maximum=400,
            fallback=DEFAULT_WEEKLY_QUESTIONS_GOAL,
        ),
        'focus_mode': _normalize_focus_mode(payload.get('focus_mode')),
        'preferred_period': _normalize_preferred_period(
            payload.get('preferred_period')
        ),
        'priority_disciplines': normalize_priority_disciplines(
            payload.get('priority_disciplines')
        ),
    }


def _payload_values_from_row(row: dict[str, object] | None) -> dict[str, object]:
    if row is None:
        return {
            'study_days_per_week': DEFAULT_STUDY_DAYS_PER_WEEK,
            'minutes_per_day': DEFAULT_MINUTES_PER_DAY,
            'weekly_questions_goal': DEFAULT_WEEKLY_QUESTIONS_GOAL,
            'focus_mode': DEFAULT_FOCUS_MODE,
            'preferred_period': DEFAULT_PREFERRED_PERIOD,
            'priority_disciplines': [],
        }

    return {
        'study_days_per_week': int(
            row.get('study_days_per_week') or DEFAULT_STUDY_DAYS_PER_WEEK
        ),
        'minutes_per_day': int(row.get('minutes_per_day') or DEFAULT_MINUTES_PER_DAY),
        'weekly_questions_goal': int(
            row.get('weekly_questions_goal') or DEFAULT_WEEKLY_QUESTIONS_GOAL
        ),
        'focus_mode': str(row.get('focus_mode') or DEFAULT_FOCUS_MODE),
        'preferred_period': str(
            row.get('preferred_period') or DEFAULT_PREFERRED_PERIOD
        ),
        'priority_disciplines': parse_priority_disciplines(
            row.get('priority_disciplines_json')
        ),
    }


def _build_payload(
    *,
    configured: bool,
    study_days_per_week: int,
    minutes_per_day: int,
    weekly_questions_goal: int,
    focus_mode: str,
    preferred_period: str,
    priority_disciplines: list[str],
    updated_at,
    weekly_metrics: dict[str, object],
) -> dict[str, object]:
    progress = (
        build_weekly_progress(
            study_days_per_week=study_days_per_week,
            minutes_per_day=minutes_per_day,
            weekly_questions_goal=weekly_questions_goal,
            focus_mode=focus_mode,
            active_days_this_week=int(weekly_metrics['active_days_this_week']),
            completed_minutes_this_week=int(
                weekly_metrics['completed_minutes_this_week']
            ),
            answered_questions_this_week=int(
                weekly_metrics['answered_questions_this_week']
            ),
        )
        if configured
        else {
            'weekly_completion_percent': 0,
            'active_days_goal': study_days_per_week,
            'active_days_percent': 0,
            'weekly_minutes_target': study_days_per_week * minutes_per_day,
            'minutes_percent': 0,
            'questions_percent': 0,
        }
    )

    return {
        'configured': configured,
        'study_days_per_week': study_days_per_week,
        'minutes_per_day': minutes_per_day,
        'weekly_questions_goal': weekly_questions_goal,
        'focus_mode': focus_mode,
        'preferred_period': preferred_period,
        'priority_disciplines': priority_disciplines,
        'week_start': weekly_metrics['week_start'].isoformat(),
        'week_end': weekly_metrics['week_end'].isoformat(),
        'active_days_this_week': int(weekly_metrics['active_days_this_week']),
        'completed_minutes_this_week': int(
            weekly_metrics['completed_minutes_this_week']
        ),
        'answered_questions_this_week': int(
            weekly_metrics['answered_questions_this_week']
        ),
        'active_days_goal': progress['active_days_goal'],
        'active_days_percent': progress['active_days_percent'],
        'weekly_minutes_target': progress['weekly_minutes_target'],
        'minutes_percent': progress['minutes_percent'],
        'questions_percent': progress['questions_percent'],
        'weekly_completion_percent': progress['weekly_completion_percent'],
        'updated_at': to_api_iso(updated_at),
    }


def fetch_study_plan(db, *, user_id: int) -> dict[str, object]:
    row = fetch_study_plan_row(db, user_id)
    weekly_metrics = fetch_weekly_metrics(db, user_id=user_id)
    values = _payload_values_from_row(row)

    return _build_payload(
        configured=row is not None,
        updated_at=None if row is None else row.get('updated_at'),
        weekly_metrics=weekly_metrics,
        **values,
    )


def preview_study_plan(
    db,
    *,
    user_id: int,
    payload: dict[str, object],
) -> dict[str, object]:
    row = fetch_study_plan_row(db, user_id)
    weekly_metrics = fetch_weekly_metrics(db, user_id=user_id)
    normalized_payload = _normalize_study_plan_payload(payload)

    return _build_payload(
        configured=row is not None,
        updated_at=None if row is None else row.get('updated_at'),
        weekly_metrics=weekly_metrics,
        **normalized_payload,
    )


def save_study_plan(
    db,
    *,
    user_id: int,
    firebase_uid: str,
    payload: dict[str, object],
) -> dict[str, object]:
    normalized_payload = _normalize_study_plan_payload(payload)

    upsert_study_plan_row(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        **normalized_payload,
    )

    return fetch_study_plan(db, user_id=user_id)

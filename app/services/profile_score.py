import json
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import to_api_iso, utc_now
from app.db.models import get_attempts_table, get_sessions_table

QUESTION_GOAL = 1500
QUESTION_POINTS_MAX = 35.0
ACCURACY_FLOOR = 40.0
ACCURACY_CEILING = 80.0
ACCURACY_POINTS_MAX = 30.0
COMPLETED_SESSION_POINTS = 2.0
COMPLETED_SESSION_POINTS_MAX = 20.0
CONSISTENCY_DAYS_WINDOW = 30
CONSISTENCY_POINTS_PER_DAY = 0.5
CONSISTENCY_POINTS_MAX = 15.0

_LEVEL_THRESHOLDS = (
    (80.0, 'Academico Avancado'),
    (60.0, 'Avancado'),
    (40.0, 'Dedicado'),
    (20.0, 'Em Evolucao'),
    (0.0, 'Iniciante'),
)


def _round_points(value: float) -> float:
    return round(float(value), 1)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


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


def _derive_level(score: float) -> str:
    for minimum_score, label in _LEVEL_THRESHOLDS:
        if score >= minimum_score:
            return label
    return 'Iniciante'


def _next_level(score: float) -> tuple[str | None, int]:
    ascending = sorted(_LEVEL_THRESHOLDS, key=lambda item: item[0])
    for minimum_score, label in ascending:
        if score < minimum_score:
            remaining = max(0, int(round(minimum_score - score)))
            return label, remaining
    return None, 0


def fetch_profile_score(db: Session, user_id: int) -> dict:
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
    accuracy_percent = round((total_correct / total_questions) * 100, 1) if total_questions else 0.0

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
    completed_sessions = sum(
        1 for row in completed_rows if _parse_completed_state(row[0])
    )
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

    questions_score = _round_points(
        min(total_questions / QUESTION_GOAL, 1.0) * QUESTION_POINTS_MAX
    )
    accuracy_progress = _clamp(
        (accuracy_percent - ACCURACY_FLOOR)
        / (ACCURACY_CEILING - ACCURACY_FLOOR),
        0.0,
        1.0,
    )
    accuracy_score = _round_points(accuracy_progress * ACCURACY_POINTS_MAX)
    completed_sessions_score = _round_points(
        min(completed_sessions * COMPLETED_SESSION_POINTS, COMPLETED_SESSION_POINTS_MAX)
    )
    consistency_score = _round_points(
        min(active_days_last_30 * CONSISTENCY_POINTS_PER_DAY, CONSISTENCY_POINTS_MAX)
    )

    exact_score = _round_points(
        min(
            questions_score
            + accuracy_score
            + completed_sessions_score
            + consistency_score,
            100.0,
        )
    )
    score = int(round(exact_score))
    level = _derive_level(exact_score)
    next_level, points_to_next_level = _next_level(exact_score)

    return {
        'score': score,
        'exact_score': exact_score,
        'level': level,
        'questions_answered': total_questions,
        'total_correct': total_correct,
        'accuracy_percent': accuracy_percent,
        'completed_sessions': completed_sessions,
        'total_study_seconds': total_study_seconds,
        'active_days_last_30': active_days_last_30,
        'consistency_window_days': CONSISTENCY_DAYS_WINDOW,
        'last_activity_at': to_api_iso(last_activity_at),
        'next_level': next_level,
        'points_to_next_level': points_to_next_level,
        'questions_by_discipline': [
            {
                'discipline': str(discipline or '').strip(),
                'count': int(count or 0),
            }
            for discipline, count in question_rows
            if str(discipline or '').strip()
        ],
        'score_breakdown': {
            'questions': {
                'points': questions_score,
                'max_points': QUESTION_POINTS_MAX,
                'raw': total_questions,
                'goal': QUESTION_GOAL,
            },
            'accuracy': {
                'points': accuracy_score,
                'max_points': ACCURACY_POINTS_MAX,
                'raw': accuracy_percent,
                'floor': ACCURACY_FLOOR,
                'ceiling': ACCURACY_CEILING,
            },
            'completed_sessions': {
                'points': completed_sessions_score,
                'max_points': COMPLETED_SESSION_POINTS_MAX,
                'raw': completed_sessions,
                'points_per_session': COMPLETED_SESSION_POINTS,
            },
            'consistency': {
                'points': consistency_score,
                'max_points': CONSISTENCY_POINTS_MAX,
                'raw': active_days_last_30,
                'window_days': CONSISTENCY_DAYS_WINDOW,
                'points_per_day': CONSISTENCY_POINTS_PER_DAY,
            },
        },
    }

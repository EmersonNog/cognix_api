import json
from datetime import timedelta

from sqlalchemy import case, func, select
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
from app.services.profile_score.constants import (
    CONSISTENCY_DAYS_WINDOW,
    RECENT_INDEX_ATTEMPT_SAMPLE_SIZE,
    SCORE_CONSISTENCY_WINDOW_DAYS,
    SCORE_RECENT_ACCURACY_WINDOW_DAYS,
    SCORE_SIMULATION_WINDOW_DAYS,
    SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD,
    SUBCATEGORY_INSIGHT_MIN_ATTEMPTS,
)


def _parse_state(state_json: str | None) -> dict:
    try:
        return json.loads(state_json or '{}')
    except json.JSONDecodeError:
        return {}



def _coerce_non_negative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0



def _session_accuracy_percent(answered_questions: int, total_questions: int, correct_answers: int) -> float:
    denominator = answered_questions if answered_questions > 0 else total_questions
    if denominator <= 0:
        return 0.0
    return round((correct_answers / denominator) * 100, 1)



def _build_subcategory_insights(
    db: Session,
    attempt_history,
    user_id: int,
) -> tuple[dict | None, dict | None, int]:
    rows = db.execute(
        select(
            attempt_history.c.discipline,
            attempt_history.c.subcategory,
            func.count().label('total_attempts'),
            func.sum(
                case((attempt_history.c.is_correct.is_(True), 1), else_=0)
            ).label('total_correct'),
        )
        .where(attempt_history.c.user_id == user_id)
        .where(attempt_history.c.discipline.is_not(None))
        .where(attempt_history.c.subcategory.is_not(None))
        .group_by(attempt_history.c.discipline, attempt_history.c.subcategory)
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



def _count_active_days(
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



def _fallback_completed_session_metrics(
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
        payload = _parse_state(state_json)
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
        total_study_seconds += _coerce_non_negative_int(
            result.get('elapsedSeconds') or payload.get('elapsedSeconds')
        )

    return {
        'completed_sessions': completed_sessions,
        'total_study_seconds': total_study_seconds,
        'recent_completed_sessions': recent_completed_sessions,
        'last_completed_at': last_completed_at,
    }



def _recent_attempt_outcomes(
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


def _latest_session_accuracy_percent(
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
    return _session_accuracy_percent(
        int(latest_answered or 0),
        int(latest_total or 0),
        int(latest_correct or 0),
    )



def _latest_timestamp(*values):
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return max(valid)



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
    active_days_last_30 = _count_active_days(
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
        _build_subcategory_insights(db, attempt_history, user_id)
    )

    recent_accuracy_cutoff = now - timedelta(days=SCORE_RECENT_ACCURACY_WINDOW_DAYS - 1)
    recent_attempt_outcomes = _recent_attempt_outcomes(
        db,
        attempt_history,
        user_id,
        recent_accuracy_cutoff,
    )

    recent_consistency_cutoff = now - timedelta(days=SCORE_CONSISTENCY_WINDOW_DAYS - 1)
    recent_active_days = _count_active_days(
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
    last_completed_session_at = db.execute(
        select(func.max(session_history.c.completed_at))
        .select_from(session_history)
        .where(session_history.c.user_id == user_id)
    ).scalar()

    if completed_sessions == 0 and total_study_seconds == 0:
        fallback_metrics = _fallback_completed_session_metrics(
            db,
            sessions,
            user_id,
            recent_sessions_cutoff,
        )
        completed_sessions = fallback_metrics['completed_sessions']
        total_study_seconds = fallback_metrics['total_study_seconds']
        recent_completed_sessions = fallback_metrics['recent_completed_sessions']
        last_completed_session_at = fallback_metrics['last_completed_at']

    latest_session_accuracy_percent = _latest_session_accuracy_percent(
        db,
        session_history,
        user_id,
    )

    last_activity_at = _latest_timestamp(
        db.execute(
            select(func.max(attempt_history.c.answered_at))
            .select_from(attempt_history)
            .where(attempt_history.c.user_id == user_id)
        ).scalar(),
        last_completed_session_at,
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
        'question_rows': question_rows,
        'strongest_subcategory': strongest_subcategory,
        'weakest_subcategory': weakest_subcategory,
        'attention_subcategories_count': attention_subcategories_count,
        'recent_attempt_outcomes': recent_attempt_outcomes,
        'recent_completed_sessions': recent_completed_sessions,
        'recent_active_days': recent_active_days,
        'latest_session_accuracy_percent': latest_session_accuracy_percent,
    }


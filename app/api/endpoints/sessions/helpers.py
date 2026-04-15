from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import to_api_iso
from app.services.session_state import derive_session_snapshot_columns, parse_session_state


def get_session_row(
    db: Session,
    sessions,
    user_id: int,
    discipline: str,
    subcategory: str,
):
    return db.execute(
        select(sessions)
        .where(sessions.c.user_id == user_id)
        .where(sessions.c.discipline == discipline)
        .where(sessions.c.subcategory == subcategory)
    ).mappings().first()


def load_state(row: dict) -> dict:
    return parse_session_state(row.get('state_json'))


def _snapshot_columns_from_row(row: dict) -> dict:
    expected_keys = {
        'state_version',
        'completed',
        'answered_questions',
        'total_questions',
        'elapsed_seconds',
        'saved_at',
    }
    if expected_keys.issubset(row):
        return {
            'state_version': row.get('state_version'),
            'completed': row.get('completed'),
            'answered_questions': row.get('answered_questions'),
            'total_questions': row.get('total_questions'),
            'elapsed_seconds': row.get('elapsed_seconds'),
            'saved_at': row.get('saved_at'),
    }
    return derive_session_snapshot_columns(load_state(row))


def resolve_session_saved_at(row: dict):
    snapshot = _snapshot_columns_from_row(row)
    return snapshot.get('saved_at') or row.get('updated_at')


def resolve_session_state_version(row: dict) -> int | None:
    snapshot = _snapshot_columns_from_row(row)
    raw_value = snapshot.get('state_version')
    try:
        return int(raw_value) if raw_value is not None else None
    except (TypeError, ValueError):
        return None


def build_session_overview_item(row: dict) -> dict:
    snapshot = _snapshot_columns_from_row(row)
    completed = snapshot.get('completed') is True
    answered_questions = int(snapshot.get('answered_questions') or 0)
    total_questions = int(snapshot.get('total_questions') or 0)
    progress = answered_questions / total_questions if total_questions > 0 else 0.0
    saved_at = snapshot.get('saved_at')
    session_at = resolve_session_saved_at(row)

    return {
        'discipline': row.get('discipline') or '',
        'subcategory': row.get('subcategory') or '',
        'completed': completed,
        'answered_questions': answered_questions,
        'total_questions': total_questions,
        'progress': progress,
        'session_at': to_api_iso(session_at),
        'saved_at': to_api_iso(saved_at),
        'updated_at': to_api_iso(row.get('updated_at')),
    }


def build_completed_history_overview_item(row: dict) -> dict:
    answered_questions = int(row.get('answered_questions') or 0)
    total_questions = int(row.get('total_questions') or 0)
    progress = answered_questions / total_questions if total_questions > 0 else 1.0
    completed_at = row.get('completed_at')
    return {
        'discipline': row.get('discipline') or '',
        'subcategory': row.get('subcategory') or '',
        'completed': True,
        'answered_questions': answered_questions,
        'total_questions': total_questions,
        'progress': progress,
        'session_at': to_api_iso(completed_at),
        'completed_at': to_api_iso(completed_at),
        'updated_at': to_api_iso(completed_at),
    }


def extract_completed_history_values(
    state: object,
    completed_at,
) -> dict | None:
    if not isinstance(state, dict) or state.get('completed') is not True:
        return None

    result = state.get('result')
    if not isinstance(result, dict):
        return None

    session_key = str(state.get('savedAt') or int(completed_at.timestamp() * 1000))
    return {
        'session_key': session_key,
        'total_questions': max(0, int(result.get('totalQuestions') or 0)),
        'answered_questions': max(0, int(result.get('answeredQuestions') or 0)),
        'correct_answers': max(0, int(result.get('correctAnswers') or 0)),
        'wrong_answers': max(0, int(result.get('wrongAnswers') or 0)),
        'elapsed_seconds': max(0, int(result.get('elapsedSeconds') or 0)),
        'completed_at': completed_at,
    }

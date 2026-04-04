import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import to_api_iso


def require_user_context(
    user_claims: dict,
    require_firebase_uid: bool = False,
) -> tuple[int, str | None]:
    internal = user_claims.get('internal_user') or {}
    user_id = internal.get('id')
    firebase_uid = user_claims.get('uid')

    if not user_id or (require_firebase_uid and not firebase_uid):
        raise HTTPException(status_code=401, detail='Unauthorized')

    return user_id, firebase_uid


def parse_state_json(state_json: str | None) -> dict:
    try:
        return json.loads(state_json or '{}')
    except json.JSONDecodeError:
        return {}


def normalize_required_text(field_name: str, value: object) -> str:
    normalized = str(value or '').strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f'{field_name} is required')
    return normalized


def serialize_state(state: object) -> str:
    if state is None:
        raise HTTPException(status_code=400, detail='state is required')

    try:
        return json.dumps(state, ensure_ascii=True)
    except TypeError:
        raise HTTPException(status_code=400, detail='state must be JSON serializable')


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
    return parse_state_json(row.get('state_json'))


def build_session_overview_item(row: dict) -> dict:
    state = load_state(row)
    completed = state.get('completed') is True
    result = state.get('result') if isinstance(state.get('result'), dict) else {}
    last_submitted = state.get('lastSubmitted')
    answered_questions = (
        int(result.get('answeredQuestions') or 0)
        if completed
        else len(last_submitted) if isinstance(last_submitted, dict) else 0
    )
    total_questions = (
        int(result.get('totalQuestions') or 0)
        if completed
        else int(state.get('totalAvailable') or 0)
    )
    progress = answered_questions / total_questions if total_questions > 0 else 0.0

    return {
        'discipline': row.get('discipline') or '',
        'subcategory': row.get('subcategory') or '',
        'completed': completed,
        'answered_questions': answered_questions,
        'total_questions': total_questions,
        'progress': progress,
        'updated_at': to_api_iso(row.get('updated_at')),
    }


def build_completed_history_overview_item(row: dict) -> dict:
    answered_questions = int(row.get('answered_questions') or 0)
    total_questions = int(row.get('total_questions') or 0)
    progress = answered_questions / total_questions if total_questions > 0 else 1.0
    return {
        'discipline': row.get('discipline') or '',
        'subcategory': row.get('subcategory') or '',
        'completed': True,
        'answered_questions': answered_questions,
        'total_questions': total_questions,
        'progress': progress,
        'updated_at': to_api_iso(row.get('completed_at')),
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

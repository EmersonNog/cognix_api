import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.datetime_utils import to_api_iso, utc_now
from app.db.models import get_sessions_table

router = APIRouter()


def _require_user_context(user_claims: dict, require_firebase_uid: bool = False) -> tuple[int, str | None]:
    internal = user_claims.get('internal_user') or {}
    user_id = internal.get('id')
    firebase_uid = user_claims.get('uid')

    if not user_id or (require_firebase_uid and not firebase_uid):
        raise HTTPException(status_code=401, detail='Unauthorized')

    return user_id, firebase_uid


def _parse_state_json(state_json: str | None) -> dict:
    try:
        return json.loads(state_json or '{}')
    except json.JSONDecodeError:
        return {}


def _normalize_required_text(field_name: str, value: object) -> str:
    normalized = str(value or '').strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f'{field_name} is required')
    return normalized


def _serialize_state(state: object) -> str:
    if state is None:
        raise HTTPException(status_code=400, detail='state is required')

    try:
        return json.dumps(state, ensure_ascii=True)
    except TypeError:
        raise HTTPException(status_code=400, detail='state must be JSON serializable')


def _get_session_row(
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


def _load_state(row: dict) -> dict:
    return _parse_state_json(row.get('state_json'))


def _build_session_overview_item(row: dict) -> dict:
    state = _load_state(row)
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


@router.post('')
def upsert_session(
    payload: dict,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = _require_user_context(user_claims, require_firebase_uid=True)
    discipline = _normalize_required_text('discipline', payload.get('discipline'))
    subcategory = _normalize_required_text('subcategory', payload.get('subcategory'))
    state_json = _serialize_state(payload.get('state'))

    sessions = get_sessions_table(settings.sessions_table)
    now = utc_now()
    insert_stmt = pg_insert(sessions).values(
        user_id=user_id,
        firebase_uid=firebase_uid,
        discipline=discipline,
        subcategory=subcategory,
        state_json=state_json,
        created_at=now,
        updated_at=now,
    )
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[
            sessions.c.user_id,
            sessions.c.discipline,
            sessions.c.subcategory,
        ],
        set_={
            'firebase_uid': firebase_uid,
            'state_json': state_json,
            'updated_at': now,
        },
    )
    db.execute(upsert_stmt)
    db.commit()
    return {'status': 'ok'}


@router.get('')
def get_session(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _ = _require_user_context(user_claims)
    sessions = get_sessions_table(settings.sessions_table)
    row = _get_session_row(db, sessions, user_id, discipline, subcategory)
    if row is None:
        raise HTTPException(status_code=404, detail='Not found')

    return {
        'state': _load_state(row),
        'updated_at': to_api_iso(row.get('updated_at')),
    }


@router.get('/overview')
def get_sessions_overview(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _ = _require_user_context(user_claims)
    sessions = get_sessions_table(settings.sessions_table)
    rows = db.execute(
        select(sessions)
        .where(sessions.c.user_id == user_id)
        .order_by(sessions.c.updated_at.desc())
    ).mappings().all()

    items = [_build_session_overview_item(row) for row in rows]
    completed_sessions = sum(1 for item in items if item['completed'])
    in_progress_sessions = sum(1 for item in items if not item['completed'])

    return {
        'completed_sessions': completed_sessions,
        'in_progress_sessions': in_progress_sessions,
        'latest_session': items[0] if items else None,
    }


@router.delete('')
def delete_session(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _ = _require_user_context(user_claims)
    sessions = get_sessions_table(settings.sessions_table)
    db.execute(
        delete(sessions)
        .where(sessions.c.user_id == user_id)
        .where(sessions.c.discipline == discipline)
        .where(sessions.c.subcategory == subcategory)
    )
    db.commit()
    return {'status': 'ok'}

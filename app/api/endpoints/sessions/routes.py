from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.datetime_utils import ensure_utc, to_api_iso, utc_now
from app.db.models import get_session_history_table, get_sessions_table

from .helpers import (
    build_completed_history_overview_item,
    build_session_overview_item,
    extract_completed_history_values,
    get_session_row,
    load_state,
    normalize_required_text,
    require_user_context,
    serialize_state,
)

router = APIRouter()


@router.post('')
def upsert_session(
    payload: dict,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    discipline = normalize_required_text('discipline', payload.get('discipline'))
    subcategory = normalize_required_text('subcategory', payload.get('subcategory'))
    state_payload = payload.get('state')
    state_json = serialize_state(state_payload)

    sessions = get_sessions_table(settings.sessions_table)
    session_history = get_session_history_table(settings.session_history_table)
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

    completed_history_values = extract_completed_history_values(state_payload, now)
    if completed_history_values is not None:
        history_insert = (
            pg_insert(session_history)
            .values(
                user_id=user_id,
                firebase_uid=firebase_uid,
                discipline=discipline,
                subcategory=subcategory,
                **completed_history_values,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    session_history.c.user_id,
                    session_history.c.discipline,
                    session_history.c.subcategory,
                    session_history.c.session_key,
                ]
            )
        )
        db.execute(history_insert)

    db.commit()
    return {'status': 'ok'}


@router.get('')
def get_session(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _ = require_user_context(user_claims)
    sessions = get_sessions_table(settings.sessions_table)
    row = get_session_row(db, sessions, user_id, discipline, subcategory)
    if row is None:
        raise HTTPException(status_code=404, detail='Not found')

    return {
        'state': load_state(row),
        'updated_at': to_api_iso(row.get('updated_at')),
    }


@router.get('/overview')
def get_sessions_overview(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _ = require_user_context(user_claims)
    sessions = get_sessions_table(settings.sessions_table)
    session_history = get_session_history_table(settings.session_history_table)
    rows = db.execute(
        select(sessions)
        .where(sessions.c.user_id == user_id)
        .order_by(sessions.c.updated_at.desc())
    ).mappings().all()

    items = [build_session_overview_item(row) for row in rows]
    in_progress_sessions = sum(1 for item in items if not item['completed'])
    completed_sessions = int(
        db.execute(
            select(func.count())
            .select_from(session_history)
            .where(session_history.c.user_id == user_id)
        ).scalar()
        or 0
    )

    latest_current_row = rows[0] if rows else None
    latest_current_item = items[0] if items else None
    latest_completed_row = db.execute(
        select(session_history)
        .where(session_history.c.user_id == user_id)
        .order_by(session_history.c.completed_at.desc())
    ).mappings().first()
    latest_completed_item = (
        build_completed_history_overview_item(latest_completed_row)
        if latest_completed_row is not None
        else None
    )

    if latest_current_row is not None and latest_completed_row is not None:
        latest_current_at = ensure_utc(latest_current_row.get('updated_at'))
        latest_completed_at = ensure_utc(latest_completed_row.get('completed_at'))
        latest_session = (
            latest_current_item
            if latest_completed_at is None
            or (latest_current_at is not None and latest_current_at >= latest_completed_at)
            else latest_completed_item
        )
    else:
        latest_session = latest_current_item or latest_completed_item

    return {
        'completed_sessions': completed_sessions,
        'in_progress_sessions': in_progress_sessions,
        'latest_session': latest_session,
    }


@router.delete('')
def delete_session(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _ = require_user_context(user_claims)
    sessions = get_sessions_table(settings.sessions_table)
    db.execute(
        delete(sessions)
        .where(sessions.c.user_id == user_id)
        .where(sessions.c.discipline == discipline)
        .where(sessions.c.subcategory == subcategory)
    )
    db.commit()
    return {'status': 'ok'}

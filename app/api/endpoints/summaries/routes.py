import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.datetime_utils import ensure_utc, utc_now
from app.db.models import (
    get_questions_table,
    get_summaries_table,
    get_user_summaries_table,
)
from app.db.session import engine
from app.services.summaries import (
    attach_stats,
    default_summary,
    fetch_question_total,
    fetch_user_stats,
    gemini_available,
    generate_personalized_summary,
    has_completed_session,
    latest_attempt_at,
    load_summary_payload,
    locked_summary,
    normalize_required_summary_fields,
    normalize_summary_payload,
    require_authenticated_user,
    require_user_id,
    upsert_base_summary,
    upsert_user_summary,
)

from .helpers import has_summary_nodes, load_base_summary

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('', dependencies=[Depends(get_current_user)])
def get_summary(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    payload = load_base_summary(db, discipline, subcategory)
    return attach_stats(payload, None)


@router.get('/personal', dependencies=[Depends(get_current_user)])
def get_personal_summary(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    auto_generate: bool = Query(True),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    logger.info(
        'Summary request discipline=%s subcategory=%s auto_generate=%s',
        discipline,
        subcategory,
        auto_generate,
    )
    user_id, firebase_uid = require_authenticated_user(user_claims)
    stats = fetch_user_stats(db, user_id, discipline, subcategory)

    if not has_completed_session(db, user_id, discipline, subcategory):
        return attach_stats(locked_summary(discipline, subcategory), stats)

    table = get_user_summaries_table(settings.user_summaries_table)
    row = db.execute(
        select(table)
        .where(table.c.user_id == user_id)
        .where(table.c.discipline == discipline)
        .where(table.c.subcategory == subcategory)
    ).mappings().first()

    if row is not None:
        latest_attempt = ensure_utc(
            latest_attempt_at(db, user_id, discipline, subcategory)
        )
        updated_at = ensure_utc(row['updated_at'])
        if latest_attempt and updated_at and latest_attempt <= updated_at:
            payload = load_summary_payload(row['payload_json'])
            if has_summary_nodes(payload):
                return attach_stats(payload, stats)

    if not auto_generate or not gemini_available():
        return attach_stats(load_base_summary(db, discipline, subcategory), stats)

    payload, stats = generate_personalized_summary(db, user_id, discipline, subcategory)
    if not has_summary_nodes(payload):
        payload = load_base_summary(db, discipline, subcategory)
    upsert_user_summary(db, user_id, firebase_uid, discipline, subcategory, payload)
    return attach_stats(payload, stats)


@router.get('/progress', dependencies=[Depends(get_current_user)])
def get_training_progress(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id = require_user_id(user_claims)
    stats = fetch_user_stats(db, user_id, discipline, subcategory)
    total_questions = fetch_question_total(db, discipline, subcategory)
    answered_questions = int(stats.get('total_attempts') or 0)
    progress = (answered_questions / total_questions) if total_questions else 0.0

    return {
        'discipline': discipline,
        'subcategory': subcategory,
        'answered_questions': answered_questions,
        'total_questions': total_questions,
        'progress': progress,
    }


@router.post('/auto_generate', dependencies=[Depends(get_current_user)])
def auto_generate_summary(
    discipline: str = Query(...),
    subcategory: str = Query(...),
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = require_authenticated_user(user_claims)

    if not has_completed_session(db, user_id, discipline, subcategory):
        raise HTTPException(
            status_code=409,
            detail='Complete o simulado antes de gerar o mapa mental',
        )

    if not gemini_available():
        raise HTTPException(status_code=500, detail='Gemini not configured')

    payload, stats = generate_personalized_summary(db, user_id, discipline, subcategory)
    if not has_summary_nodes(payload):
        payload = load_base_summary(db, discipline, subcategory)
    upsert_user_summary(db, user_id, firebase_uid, discipline, subcategory, payload)
    return attach_stats(payload, stats)


@router.post('', dependencies=[Depends(get_current_user)])
def upsert_summary(
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    discipline, subcategory, nodes, title = normalize_required_summary_fields(payload)

    normalized_payload = normalize_summary_payload(
        {
            'title': title or f'{subcategory} - Resumo',
            'discipline': discipline,
            'subcategory': subcategory,
            'nodes': nodes,
        }
    )
    upsert_base_summary(db, discipline, subcategory, normalized_payload)
    return {'status': 'ok'}


@router.post('/bootstrap', dependencies=[Depends(get_current_user)])
def bootstrap_summaries(db: Session = Depends(get_db)) -> dict:
    table = get_questions_table(engine, settings.question_table)
    if 'disciplina' not in table.c or 'subcategoria' not in table.c:
        raise HTTPException(status_code=500, detail='Missing columns for bootstrap')

    rows = db.execute(
        select(table.c.disciplina, table.c.subcategoria)
        .where(table.c.disciplina.is_not(None))
        .where(table.c.subcategoria.is_not(None))
        .distinct()
    ).all()

    summaries = get_summaries_table(settings.summaries_table)
    now = utc_now()
    created = 0
    for discipline, subcategory in rows:
        if not str(discipline).strip() or not str(subcategory).strip():
            continue
        payload = default_summary(str(discipline).strip(), str(subcategory).strip())
        insert_stmt = pg_insert(summaries).values(
            discipline=str(discipline).strip(),
            subcategory=str(subcategory).strip(),
            payload_json=json.dumps(payload, ensure_ascii=True),
            created_at=now,
            updated_at=now,
        )
        result = db.execute(
            insert_stmt.on_conflict_do_nothing(
                index_elements=[summaries.c.discipline, summaries.c.subcategory]
            )
        )
        if result.rowcount:
            created += 1
    db.commit()
    return {'status': 'ok', 'created': created}

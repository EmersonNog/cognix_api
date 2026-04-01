from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models import get_attempts_table, get_questions_table
from app.db.session import engine

router = APIRouter()

def _require_authenticated_user(user_claims: dict) -> tuple[int, str]:
    internal = user_claims.get('internal_user') or {}
    user_id = internal.get('id')
    firebase_uid = user_claims.get('uid')
    if not user_id or not firebase_uid:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return user_id, firebase_uid

def _parse_attempt_payload(payload: dict) -> tuple[object, str, str | None, str | None]:
    question_id = payload.get('question_id')
    selected_letter = payload.get('selected_letter')
    discipline = payload.get('discipline')
    subcategory = payload.get('subcategory')

    if question_id is None or not str(question_id).strip():
        raise HTTPException(status_code=400, detail='question_id is required')
    if selected_letter is None or not str(selected_letter).strip():
        raise HTTPException(status_code=400, detail='selected_letter is required')

    normalized_letter = str(selected_letter).strip().upper()[:2]
    return question_id, normalized_letter, discipline, subcategory

def _fetch_correct_letter(db: Session, question_id: object) -> str | None:
    questions = get_questions_table(engine, settings.question_table)
    if 'gabarito' not in questions.c:
        return None

    row = db.execute(
        select(questions.c.gabarito).where(questions.c.id == question_id)
    ).first()
    if row is None or row[0] is None:
        return None
    return str(row[0]).strip().upper()[:2]

def _resolve_is_correct(selected_letter: str, correct_letter: str | None) -> bool | None:
    if not correct_letter:
        return None
    return selected_letter == correct_letter

@router.post('')
def upsert_attempt(
    payload: dict,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = _require_authenticated_user(user_claims)
    question_id, selected_letter, discipline, subcategory = _parse_attempt_payload(
        payload
    )

    correct_letter = _fetch_correct_letter(db, question_id)
    is_correct = _resolve_is_correct(selected_letter, correct_letter)

    attempts = get_attempts_table(settings.attempts_table)
    now = utc_now()

    insert_stmt = pg_insert(attempts).values(
        user_id=user_id,
        firebase_uid=firebase_uid,
        question_id=question_id,
        selected_letter=selected_letter,
        is_correct=is_correct,
        discipline=discipline,
        subcategory=subcategory,
        answered_at=now,
    )
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[attempts.c.user_id, attempts.c.question_id],
        set_={
            'firebase_uid': firebase_uid,
            'selected_letter': selected_letter,
            'is_correct': is_correct,
            'discipline': discipline,
            'subcategory': subcategory,
            'answered_at': now,
        },
    )

    db.execute(upsert_stmt)
    db.commit()

    return {
        'status': 'ok',
        'question_id': question_id,
        'selected_letter': selected_letter,
        'is_correct': is_correct,
        'correct_letter': correct_letter,
    }

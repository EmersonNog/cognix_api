from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.deps.entitlements import require_full_access
from app.api.endpoints.helpers import normalize_required_text, require_user_context
from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models import (
    get_attempt_history_table,
    get_attempts_table,
    get_questions_table,
)
from app.db.session import engine
from app.services.economy import sync_attempt_reward

router = APIRouter(dependencies=[Depends(require_full_access)])


def _parse_attempt_payload(payload: dict) -> tuple[object, str, str | None, str | None]:
    question_id = normalize_required_text('question_id', payload.get('question_id'))
    selected_letter = normalize_required_text(
        'selected_letter',
        payload.get('selected_letter'),
    )
    discipline = payload.get('discipline')
    subcategory = payload.get('subcategory')

    normalized_letter = selected_letter.upper()[:2]
    return question_id, normalized_letter, discipline, subcategory


def _fetch_question_lookup(
    db: Session,
    question_id: object,
) -> tuple[bool, str | None]:
    questions = get_questions_table(engine, settings.question_table)
    columns = [questions.c.id]
    has_answer_key = 'gabarito' in questions.c
    if has_answer_key:
        columns.append(questions.c.gabarito)

    row = db.execute(select(*columns).where(questions.c.id == question_id)).first()
    if row is None:
        return False, None
    if not has_answer_key or row[1] is None:
        return True, None
    return True, str(row[1]).strip().upper()[:2]


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
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    question_id, selected_letter, discipline, subcategory = _parse_attempt_payload(
        payload
    )

    try:
        resolved_question_id = int(str(question_id).strip())
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail='question_id must be numeric')
    question_exists, correct_letter = _fetch_question_lookup(
        db,
        resolved_question_id,
    )
    if not question_exists:
        raise HTTPException(status_code=404, detail='Question not found')
    is_correct = _resolve_is_correct(selected_letter, correct_letter)

    attempts = get_attempts_table(settings.attempts_table)
    attempt_history = get_attempt_history_table(settings.attempt_history_table)
    now = utc_now()
    existing_attempt = db.execute(
        select(attempts.c.id).where(
            attempts.c.user_id == user_id,
            attempts.c.question_id == resolved_question_id,
        )
    ).first()

    db.execute(
        attempt_history.insert().values(
            user_id=user_id,
            firebase_uid=firebase_uid,
            question_id=resolved_question_id,
            selected_letter=selected_letter,
            is_correct=is_correct,
            discipline=discipline,
            subcategory=subcategory,
            answered_at=now,
        )
    )

    insert_stmt = pg_insert(attempts).values(
        user_id=user_id,
        firebase_uid=firebase_uid,
        question_id=resolved_question_id,
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
    economy_state = sync_attempt_reward(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        question_id=resolved_question_id,
        eligible_for_reward=existing_attempt is None,
    )
    db.commit()

    return {
        'status': 'ok',
        'question_id': resolved_question_id,
        'selected_letter': selected_letter,
        'is_correct': is_correct,
        'correct_letter': correct_letter,
        'coins_awarded': economy_state['coins_awarded'],
        'coins_awarded_half_units': economy_state['coins_awarded_half_units'],
        'coins_reward_applied': economy_state['coins_reward_applied'],
        'coins_balance': economy_state['coins_balance'],
        'coins_half_units': economy_state['coins_half_units'],
    }

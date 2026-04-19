from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now

from .constants import (
    ANSWER_SCORE_POINTS,
    PARTICIPANT_STATUS_JOINED,
    ROOM_STATUS_IN_PROGRESS,
)
from . import tables
from .queries import fetch_room_row, joined_participants_count
from .questions import (
    fetch_question_answer_key,
    normalize_question_ids,
    resolve_is_correct,
)
from .rounds import advance_round
from .serializers import serialize_room


def submit_answer(
    db: Session,
    *,
    room_id: int,
    user_id: int,
    question_id: int,
    selected_letter: str,
) -> dict:
    room = dict(fetch_room_row(db, room_id))
    if room['status'] != ROOM_STATUS_IN_PROGRESS:
        raise HTTPException(status_code=409, detail='Room is not in progress')

    question_ids = normalize_question_ids(room.get('question_ids'))
    current_question_index = int(room.get('current_question_index') or 0)
    if not question_ids or current_question_index >= len(question_ids):
        raise HTTPException(status_code=409, detail='Room has no active question')

    active_question_id = int(question_ids[current_question_index])
    if question_id != active_question_id:
        raise HTTPException(status_code=409, detail='Question is not active')

    participants = tables.participants_table()
    participant = db.execute(
        select(participants).where(
            participants.c.room_id == room_id,
            participants.c.user_id == user_id,
            participants.c.status == PARTICIPANT_STATUS_JOINED,
        )
    ).mappings().first()
    if participant is None:
        raise HTTPException(status_code=404, detail='Participant not found')
    if bool(participant.get('answered_current_question')):
        raise HTTPException(status_code=409, detail='Question already answered')

    question_exists, correct_letter = fetch_question_answer_key(db, question_id)
    if not question_exists:
        raise HTTPException(status_code=404, detail='Question not found')

    normalized_letter = selected_letter.strip().upper()[:2]
    is_correct = resolve_is_correct(normalized_letter, correct_letter)
    score = int(participant.get('score') or 0)
    correct_answers = int(participant.get('correct_answers') or 0)
    if is_correct is True:
        score += ANSWER_SCORE_POINTS
        correct_answers += 1

    now = utc_now()
    db.execute(
        participants.update()
        .where(participants.c.id == participant['id'])
        .values(
            score=score,
            correct_answers=correct_answers,
            answered_current_question=True,
            current_question_id=question_id,
            selected_letter=normalized_letter,
            last_answered_at=now,
            updated_at=now,
        )
    )

    answered_count = int(
        db.execute(
            select(func.count()).select_from(participants).where(
                participants.c.room_id == room_id,
                participants.c.status == PARTICIPANT_STATUS_JOINED,
                participants.c.answered_current_question.is_(True),
            )
        ).scalar_one()
    )
    joined_count = joined_participants_count(db, room_id)
    should_advance = answered_count >= joined_count and joined_count > 0
    if should_advance:
        advance_round(
            db,
            room_id=room_id,
            current_question_index=current_question_index,
            question_ids=question_ids,
            now=now,
        )

    db.commit()
    return {
        'status': 'ok',
        'question_id': question_id,
        'selected_letter': normalized_letter,
        'is_correct': is_correct,
        'correct_letter': correct_letter,
        'score': score,
        'room': serialize_room(db, room_id),
    }

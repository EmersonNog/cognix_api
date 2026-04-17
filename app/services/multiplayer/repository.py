import random
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import ensure_utc, to_api_iso, utc_now
from app.db.models import (
    get_multiplayer_participants_table,
    get_multiplayer_rooms_table,
    get_questions_table,
)
from app.db.session import engine

ROOM_STATUS_WAITING = 'waiting'
ROOM_STATUS_IN_PROGRESS = 'in_progress'
ROOM_STATUS_FINISHED = 'finished'
PARTICIPANT_STATUS_JOINED = 'joined'
ROLE_HOST = 'host'
ROLE_PLAYER = 'player'
DEFAULT_ROUND_DURATION_SECONDS = 60
DEFAULT_MATCH_QUESTION_LIMIT = 10
ANSWER_SCORE_POINTS = 100


def _rooms_table():
    return get_multiplayer_rooms_table(settings.multiplayer_rooms_table)


def _participants_table():
    return get_multiplayer_participants_table(settings.multiplayer_participants_table)


def _questions_table():
    return get_questions_table(engine, settings.question_table)


def _generate_pin(db: Session) -> str:
    rooms = _rooms_table()
    for _ in range(20):
        pin = f'{random.randint(100000, 999999)}'
        exists = db.execute(select(rooms.c.id).where(rooms.c.pin == pin)).first()
        if exists is None:
            return pin
    raise HTTPException(status_code=500, detail='Could not allocate room pin')


def _fetch_room_row(db: Session, room_id: int):
    rooms = _rooms_table()
    row = db.execute(select(rooms).where(rooms.c.id == room_id)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail='Room not found')
    return row


def _fetch_room_by_pin_row(db: Session, pin: str):
    rooms = _rooms_table()
    row = db.execute(select(rooms).where(rooms.c.pin == pin)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail='Room not found')
    return row


def _joined_participants_count(db: Session, room_id: int) -> int:
    participants = _participants_table()
    return int(
        db.execute(
            select(func.count()).select_from(participants).where(
                participants.c.room_id == room_id,
                participants.c.status == PARTICIPANT_STATUS_JOINED,
            )
        ).scalar_one()
    )


def _delete_room(db: Session, room_id: int) -> None:
    participants = _participants_table()
    rooms = _rooms_table()
    db.execute(participants.delete().where(participants.c.room_id == room_id))
    db.execute(rooms.delete().where(rooms.c.id == room_id))


def _delete_empty_room(db: Session, room_id: int) -> bool:
    if _joined_participants_count(db, room_id) > 0:
        return False
    _delete_room(db, room_id)
    return True


def _require_host(room: dict[str, Any], user_id: int) -> None:
    if int(room['host_user_id']) != user_id:
        raise HTTPException(status_code=403, detail='Only room host can do this')


def _normalize_question_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []

    question_ids: list[int] = []
    for item in value:
        try:
            question_id = int(str(item).strip())
        except (TypeError, ValueError):
            continue
        if question_id > 0:
            question_ids.append(question_id)
    return question_ids


def _fetch_match_question_ids(db: Session) -> list[int]:
    questions = _questions_table()
    rows = db.execute(
        select(questions.c.id).order_by(func.random()).limit(DEFAULT_MATCH_QUESTION_LIMIT)
    ).all()
    return [int(row[0]) for row in rows]


def _fetch_question_answer_key(
    db: Session,
    question_id: int,
) -> tuple[bool, str | None]:
    questions = _questions_table()
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


def _advance_round(
    db: Session,
    *,
    room_id: int,
    current_question_index: int,
    question_ids: list[int],
    now,
) -> bool:
    if current_question_index >= len(question_ids) - 1:
        rooms = _rooms_table()
        db.execute(
            rooms.update()
            .where(rooms.c.id == room_id)
            .values(status=ROOM_STATUS_FINISHED, finished_at=now, updated_at=now)
        )
        return True

    rooms = _rooms_table()
    participants = _participants_table()
    db.execute(
        rooms.update()
        .where(rooms.c.id == room_id)
        .values(
            current_question_index=current_question_index + 1,
            round_started_at=now,
            updated_at=now,
        )
    )
    db.execute(
        participants.update()
        .where(
            participants.c.room_id == room_id,
            participants.c.status == PARTICIPANT_STATUS_JOINED,
        )
        .values(
            answered_current_question=False,
            current_question_id=None,
            selected_letter=None,
            last_answered_at=None,
            updated_at=now,
        )
    )
    return True


def _advance_room_if_round_expired(db: Session, room: dict[str, Any]) -> bool:
    if room['status'] != ROOM_STATUS_IN_PROGRESS:
        return False

    question_ids = _normalize_question_ids(room.get('question_ids'))
    current_question_index = int(room.get('current_question_index') or 0)
    round_started_at = room.get('round_started_at') or room.get('started_at')
    if (
        not question_ids
        or round_started_at is None
    ):
        return False

    duration = int(room.get('round_duration_seconds') or DEFAULT_ROUND_DURATION_SECONDS)
    now = utc_now()
    normalized_round_started_at = ensure_utc(round_started_at)
    if normalized_round_started_at is None:
        return False
    if now < normalized_round_started_at + timedelta(seconds=duration):
        return False

    advanced = _advance_round(
        db,
        room_id=int(room['id']),
        current_question_index=current_question_index,
        question_ids=question_ids,
        now=now,
    )
    if advanced:
        db.commit()
    return advanced


def _serialize_participant(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': row['id'],
        'room_id': row['room_id'],
        'user_id': row['user_id'],
        'firebase_uid': row['firebase_uid'],
        'display_name': row.get('display_name') or 'Jogador',
        'role': row['role'],
        'status': row['status'],
        'score': int(row.get('score') or 0),
        'correct_answers': int(row.get('correct_answers') or 0),
        'answered_current_question': bool(row.get('answered_current_question')),
        'current_question_id': row.get('current_question_id'),
        'selected_letter': row.get('selected_letter'),
        'joined_at': to_api_iso(row.get('joined_at')),
        'removed_at': to_api_iso(row.get('removed_at')),
        'created_at': to_api_iso(row.get('created_at')),
        'updated_at': to_api_iso(row.get('updated_at')),
    }


def _serialize_room(
    room: dict[str, Any],
    participant_rows: list[dict[str, Any]],
) -> dict:
    participants = [_serialize_participant(row) for row in participant_rows]
    question_ids = _normalize_question_ids(room.get('question_ids'))
    return {
        'id': room['id'],
        'pin': room['pin'],
        'host_user_id': room['host_user_id'],
        'host_firebase_uid': room['host_firebase_uid'],
        'status': room['status'],
        'max_participants': room['max_participants'],
        'participant_count': len(participants),
        'question_ids': question_ids,
        'current_question_index': int(room.get('current_question_index') or 0),
        'round_duration_seconds': int(
            room.get('round_duration_seconds') or DEFAULT_ROUND_DURATION_SECONDS
        ),
        'participants': participants,
        'started_at': to_api_iso(room.get('started_at')),
        'round_started_at': to_api_iso(room.get('round_started_at')),
        'finished_at': to_api_iso(room.get('finished_at')),
        'created_at': to_api_iso(room.get('created_at')),
        'updated_at': to_api_iso(room.get('updated_at')),
    }


def serialize_room(db: Session, room_id: int) -> dict:
    participants = _participants_table()
    room = dict(_fetch_room_row(db, room_id))
    if _advance_room_if_round_expired(db, room):
        room = dict(_fetch_room_row(db, room_id))
    participant_rows = [
        dict(row)
        for row in db.execute(
            select(participants).where(
                participants.c.room_id == room_id,
                participants.c.status == PARTICIPANT_STATUS_JOINED,
            ).order_by(participants.c.joined_at.asc(), participants.c.id.asc())
        ).mappings().all()
    ]
    return _serialize_room(room, participant_rows)


def create_room(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    display_name: str,
    max_participants: int,
) -> dict:
    rooms = _rooms_table()
    participants = _participants_table()
    now = utc_now()
    pin = _generate_pin(db)

    room_id = int(
        db.execute(
            rooms.insert()
            .values(
                pin=pin,
                host_user_id=user_id,
                host_firebase_uid=firebase_uid,
                status=ROOM_STATUS_WAITING,
                max_participants=max_participants,
                created_at=now,
                updated_at=now,
            )
            .returning(rooms.c.id)
        ).scalar_one()
    )
    db.execute(
        participants.insert().values(
            room_id=room_id,
            user_id=user_id,
            firebase_uid=firebase_uid,
            display_name=display_name,
            role=ROLE_HOST,
            status=PARTICIPANT_STATUS_JOINED,
            joined_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    return serialize_room(db, room_id)


def get_room_by_id(db: Session, room_id: int) -> dict:
    return serialize_room(db, room_id)


def get_room_by_pin(db: Session, pin: str) -> dict:
    room = _fetch_room_by_pin_row(db, pin)
    return serialize_room(db, int(room['id']))


def join_room(
    db: Session,
    *,
    pin: str,
    user_id: int,
    firebase_uid: str,
    display_name: str,
) -> dict:
    room = dict(_fetch_room_by_pin_row(db, pin))
    if room['status'] != ROOM_STATUS_WAITING:
        raise HTTPException(status_code=409, detail='Room is not accepting players')

    room_id = int(room['id'])
    participants = _participants_table()
    existing_participant = db.execute(
        select(participants).where(
            participants.c.room_id == room_id,
            participants.c.user_id == user_id,
        )
    ).mappings().first()
    if (
        existing_participant is not None
        and existing_participant['status'] == PARTICIPANT_STATUS_JOINED
    ):
        return serialize_room(db, room_id)

    if _joined_participants_count(db, room_id) >= int(room['max_participants']):
        raise HTTPException(status_code=409, detail='Room is full')

    now = utc_now()
    insert_stmt = pg_insert(participants).values(
        room_id=room_id,
        user_id=user_id,
        firebase_uid=firebase_uid,
        display_name=display_name,
        role=ROLE_PLAYER,
        status=PARTICIPANT_STATUS_JOINED,
        joined_at=now,
        removed_at=None,
        score=0,
        correct_answers=0,
        answered_current_question=False,
        current_question_id=None,
        selected_letter=None,
        last_answered_at=None,
        created_at=now,
        updated_at=now,
    )
    db.execute(
        insert_stmt.on_conflict_do_update(
            index_elements=[participants.c.room_id, participants.c.user_id],
            set_={
                'firebase_uid': firebase_uid,
                'display_name': display_name,
                'role': ROLE_PLAYER,
                'status': PARTICIPANT_STATUS_JOINED,
                'joined_at': now,
                'removed_at': None,
                'score': 0,
                'correct_answers': 0,
                'answered_current_question': False,
                'current_question_id': None,
                'selected_letter': None,
                'last_answered_at': None,
                'updated_at': now,
            },
        )
    )
    db.commit()
    return serialize_room(db, room_id)


def remove_participant(
    db: Session,
    *,
    room_id: int,
    participant_id: int,
    host_user_id: int,
) -> dict:
    room = dict(_fetch_room_row(db, room_id))
    _require_host(room, host_user_id)
    if room['status'] != ROOM_STATUS_WAITING:
        raise HTTPException(status_code=409, detail='Room already started')

    participants = _participants_table()
    participant = db.execute(
        select(participants).where(
            participants.c.id == participant_id,
            participants.c.room_id == room_id,
        )
    ).mappings().first()
    if participant is None:
        raise HTTPException(status_code=404, detail='Participant not found')
    if participant['role'] == ROLE_HOST:
        raise HTTPException(status_code=400, detail='Host cannot be removed')

    db.execute(participants.delete().where(participants.c.id == participant_id))
    _delete_empty_room(db, room_id)
    db.commit()
    return serialize_room(db, room_id)


def leave_room(db: Session, *, room_id: int, user_id: int) -> dict:
    room = dict(_fetch_room_row(db, room_id))
    if int(room['host_user_id']) == user_id:
        _delete_room(db, room_id)
        db.commit()
        return {'status': 'closed', 'room_id': room_id}

    participants = _participants_table()
    result = db.execute(
        participants.delete().where(
            participants.c.room_id == room_id,
            participants.c.user_id == user_id,
            participants.c.status == PARTICIPANT_STATUS_JOINED,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail='Participant not found')
    room_was_closed = _delete_empty_room(db, room_id)
    db.commit()
    if room_was_closed:
        return {'status': 'closed', 'room_id': room_id}
    return serialize_room(db, room_id)


def start_room(db: Session, *, room_id: int, host_user_id: int) -> dict:
    room = dict(_fetch_room_row(db, room_id))
    _require_host(room, host_user_id)
    if room['status'] != ROOM_STATUS_WAITING:
        raise HTTPException(status_code=409, detail='Room already started')
    if _joined_participants_count(db, room_id) < 2:
        raise HTTPException(status_code=409, detail='Need at least 2 players')

    rooms = _rooms_table()
    participants = _participants_table()
    question_ids = _fetch_match_question_ids(db)
    if not question_ids:
        raise HTTPException(status_code=409, detail='No questions available')

    now = utc_now()
    db.execute(
        rooms.update()
        .where(rooms.c.id == room_id)
        .values(
            status=ROOM_STATUS_IN_PROGRESS,
            question_ids=question_ids,
            current_question_index=0,
            round_duration_seconds=DEFAULT_ROUND_DURATION_SECONDS,
            round_started_at=now,
            started_at=now,
            updated_at=now,
        )
    )
    db.execute(
        participants.update()
        .where(
            participants.c.room_id == room_id,
            participants.c.status == PARTICIPANT_STATUS_JOINED,
        )
        .values(
            score=0,
            correct_answers=0,
            answered_current_question=False,
            current_question_id=None,
            selected_letter=None,
            last_answered_at=None,
            updated_at=now,
        )
    )
    db.commit()
    return serialize_room(db, room_id)


def submit_answer(
    db: Session,
    *,
    room_id: int,
    user_id: int,
    question_id: int,
    selected_letter: str,
) -> dict:
    room = dict(_fetch_room_row(db, room_id))
    if room['status'] != ROOM_STATUS_IN_PROGRESS:
        raise HTTPException(status_code=409, detail='Room is not in progress')

    question_ids = _normalize_question_ids(room.get('question_ids'))
    current_question_index = int(room.get('current_question_index') or 0)
    if not question_ids or current_question_index >= len(question_ids):
        raise HTTPException(status_code=409, detail='Room has no active question')

    active_question_id = int(question_ids[current_question_index])
    if question_id != active_question_id:
        raise HTTPException(status_code=409, detail='Question is not active')

    participants = _participants_table()
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

    question_exists, correct_letter = _fetch_question_answer_key(db, question_id)
    if not question_exists:
        raise HTTPException(status_code=404, detail='Question not found')

    normalized_letter = selected_letter.strip().upper()[:2]
    is_correct = _resolve_is_correct(normalized_letter, correct_letter)
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
    joined_count = _joined_participants_count(db, room_id)
    should_advance = answered_count >= joined_count and joined_count > 0
    if should_advance:
        _advance_round(
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

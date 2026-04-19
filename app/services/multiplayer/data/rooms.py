from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now

from .constants import (
    DEFAULT_ROUND_DURATION_SECONDS,
    PARTICIPANT_STATUS_JOINED,
    ROLE_HOST,
    ROLE_PLAYER,
    ROOM_CLOSED_REASON_HOST_LEFT,
    ROOM_CLOSED_REASON_HOST_OFFLINE,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_WAITING,
)
from . import tables
from .queries import (
    fetch_room_by_pin_row,
    fetch_room_row,
    generate_pin,
    joined_participants_count,
    require_host,
)
from .questions import fetch_match_question_ids
from .rounds import advance_room_after_participant_exit
from .serializers import serialize_closed_room, serialize_room


def delete_room(db: Session, room_id: int) -> None:
    participants = tables.participants_table()
    rooms = tables.rooms_table()
    db.execute(participants.delete().where(participants.c.room_id == room_id))
    db.execute(rooms.delete().where(rooms.c.id == room_id))


def delete_empty_room(db: Session, room_id: int) -> bool:
    if joined_participants_count(db, room_id) > 0:
        return False
    delete_room(db, room_id)
    return True


def create_room(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    display_name: str,
    max_participants: int,
) -> dict:
    rooms = tables.rooms_table()
    participants = tables.participants_table()
    now = utc_now()
    pin = generate_pin(db)

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
    room = fetch_room_by_pin_row(db, pin)
    return serialize_room(db, int(room['id']))


def join_room(
    db: Session,
    *,
    pin: str,
    user_id: int,
    firebase_uid: str,
    display_name: str,
) -> dict:
    room = dict(fetch_room_by_pin_row(db, pin))
    room_id = int(room['id'])
    participants = tables.participants_table()
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

    if room['status'] != ROOM_STATUS_WAITING:
        raise HTTPException(status_code=409, detail='Room is not accepting players')

    if joined_participants_count(db, room_id) >= int(room['max_participants']):
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
    room = dict(fetch_room_row(db, room_id))
    require_host(room, host_user_id)
    if room['status'] != ROOM_STATUS_WAITING:
        raise HTTPException(status_code=409, detail='Room already started')

    participants = tables.participants_table()
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
    delete_empty_room(db, room_id)
    db.commit()
    return serialize_room(db, room_id)


def leave_room(db: Session, *, room_id: int, user_id: int) -> dict:
    room = dict(fetch_room_row(db, room_id))
    if int(room['host_user_id']) == user_id:
        snapshot = serialize_closed_room(db, room, reason=ROOM_CLOSED_REASON_HOST_LEFT)
        delete_room(db, room_id)
        db.commit()
        return snapshot

    participants = tables.participants_table()
    result = db.execute(
        participants.delete().where(
            participants.c.room_id == room_id,
            participants.c.user_id == user_id,
            participants.c.status == PARTICIPANT_STATUS_JOINED,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail='Participant not found')
    if room['status'] == ROOM_STATUS_IN_PROGRESS:
        advance_room_after_participant_exit(db, room_id=room_id)
    room_was_closed = delete_empty_room(db, room_id)
    db.commit()
    if room_was_closed:
        return {'status': 'closed', 'room_id': room_id}
    return serialize_room(db, room_id)


def close_room_for_host_disconnect(
    db: Session,
    *,
    room_id: int,
    host_user_id: int,
) -> dict | None:
    room = dict(fetch_room_row(db, room_id))
    if int(room['host_user_id']) != host_user_id:
        return None
    snapshot = serialize_closed_room(
        db,
        room,
        reason=ROOM_CLOSED_REASON_HOST_OFFLINE,
    )
    delete_room(db, room_id)
    db.commit()
    return snapshot


def start_room(db: Session, *, room_id: int, host_user_id: int) -> dict:
    room = dict(fetch_room_row(db, room_id))
    require_host(room, host_user_id)
    if room['status'] != ROOM_STATUS_WAITING:
        raise HTTPException(status_code=409, detail='Room already started')
    if joined_participants_count(db, room_id) < 2:
        raise HTTPException(status_code=409, detail='Need at least 2 players')

    rooms = tables.rooms_table()
    participants = tables.participants_table()
    question_ids = fetch_match_question_ids(db)
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

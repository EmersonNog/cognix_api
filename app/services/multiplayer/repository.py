import random
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import to_api_iso, utc_now
from app.db.models import (
    get_multiplayer_participants_table,
    get_multiplayer_rooms_table,
)

ROOM_STATUS_WAITING = 'waiting'
ROOM_STATUS_IN_PROGRESS = 'in_progress'
PARTICIPANT_STATUS_JOINED = 'joined'
ROLE_HOST = 'host'
ROLE_PLAYER = 'player'


def _rooms_table():
    return get_multiplayer_rooms_table(settings.multiplayer_rooms_table)


def _participants_table():
    return get_multiplayer_participants_table(settings.multiplayer_participants_table)


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


def _serialize_participant(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': row['id'],
        'room_id': row['room_id'],
        'user_id': row['user_id'],
        'firebase_uid': row['firebase_uid'],
        'display_name': row.get('display_name') or 'Jogador',
        'role': row['role'],
        'status': row['status'],
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
    return {
        'id': room['id'],
        'pin': room['pin'],
        'host_user_id': room['host_user_id'],
        'host_firebase_uid': room['host_firebase_uid'],
        'status': room['status'],
        'max_participants': room['max_participants'],
        'participant_count': len(participants),
        'participants': participants,
        'started_at': to_api_iso(room.get('started_at')),
        'finished_at': to_api_iso(room.get('finished_at')),
        'created_at': to_api_iso(room.get('created_at')),
        'updated_at': to_api_iso(room.get('updated_at')),
    }


def serialize_room(db: Session, room_id: int) -> dict:
    participants = _participants_table()
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
    now = utc_now()
    db.execute(
        rooms.update()
        .where(rooms.c.id == room_id)
        .values(status=ROOM_STATUS_IN_PROGRESS, started_at=now, updated_at=now)
    )
    db.commit()
    return serialize_room(db, room_id)

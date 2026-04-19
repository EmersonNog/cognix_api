import random
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .constants import PARTICIPANT_STATUS_JOINED
from . import tables


def generate_pin(db: Session) -> str:
    rooms = tables.rooms_table()
    for _ in range(20):
        pin = f'{random.randint(100000, 999999)}'
        exists = db.execute(select(rooms.c.id).where(rooms.c.pin == pin)).first()
        if exists is None:
            return pin
    raise HTTPException(status_code=500, detail='Could not allocate room pin')


def fetch_room_row(db: Session, room_id: int):
    rooms = tables.rooms_table()
    row = db.execute(select(rooms).where(rooms.c.id == room_id)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail='Room not found')
    return row


def fetch_room_by_pin_row(db: Session, pin: str):
    rooms = tables.rooms_table()
    row = db.execute(select(rooms).where(rooms.c.pin == pin)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail='Room not found')
    return row


def joined_participants_count(db: Session, room_id: int) -> int:
    participants = tables.participants_table()
    return int(
        db.execute(
            select(func.count()).select_from(participants).where(
                participants.c.room_id == room_id,
                participants.c.status == PARTICIPANT_STATUS_JOINED,
            )
        ).scalar_one()
    )


def require_host(room: dict[str, Any], user_id: int) -> None:
    if int(room['host_user_id']) != user_id:
        raise HTTPException(status_code=403, detail='Only room host can do this')

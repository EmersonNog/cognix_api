from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import ensure_utc, utc_now

from .constants import (
    DEFAULT_ROUND_DURATION_SECONDS,
    PARTICIPANT_STATUS_JOINED,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
)
from . import tables
from .queries import fetch_room_row, joined_participants_count
from .questions import normalize_question_ids


def advance_round(
    db: Session,
    *,
    room_id: int,
    current_question_index: int,
    question_ids: list[int],
    now,
) -> bool:
    if current_question_index >= len(question_ids) - 1:
        rooms = tables.rooms_table()
        db.execute(
            rooms.update()
            .where(rooms.c.id == room_id)
            .values(status=ROOM_STATUS_FINISHED, finished_at=now, updated_at=now)
        )
        return True

    rooms = tables.rooms_table()
    participants = tables.participants_table()
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


def advance_room_if_round_expired(db: Session, room: dict[str, Any]) -> bool:
    if room['status'] != ROOM_STATUS_IN_PROGRESS:
        return False

    question_ids = normalize_question_ids(room.get('question_ids'))
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

    advanced = advance_round(
        db,
        room_id=int(room['id']),
        current_question_index=current_question_index,
        question_ids=question_ids,
        now=now,
    )
    if advanced:
        db.commit()
    return advanced


def advance_room_after_participant_exit(db: Session, *, room_id: int) -> bool:
    room = dict(fetch_room_row(db, room_id))
    if room['status'] != ROOM_STATUS_IN_PROGRESS:
        return False

    participants = tables.participants_table()
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
    if joined_count <= 0 or answered_count < joined_count:
        return False

    question_ids = normalize_question_ids(room.get('question_ids'))
    current_question_index = int(room.get('current_question_index') or 0)
    advance_round(
        db,
        room_id=room_id,
        current_question_index=current_question_index,
        question_ids=question_ids,
        now=utc_now(),
    )
    return True

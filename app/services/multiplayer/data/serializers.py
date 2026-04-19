from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import to_api_iso, utc_now

from .constants import (
    DEFAULT_ROUND_DURATION_SECONDS,
    PARTICIPANT_STATUS_JOINED,
)
from . import tables
from .queries import fetch_room_row
from .questions import normalize_question_ids
from .rounds import advance_room_if_round_expired


def serialize_participant(row: dict[str, Any]) -> dict[str, Any]:
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


def participant_sort_key(participant: dict[str, Any]) -> tuple[int, int, str]:
    return (
        -int(participant.get('score') or 0),
        -int(participant.get('correct_answers') or 0),
        str(participant.get('display_name') or 'Jogador').strip().lower(),
    )


def serialize_room_snapshot(
    room: dict[str, Any],
    participant_rows: list[dict[str, Any]],
) -> dict:
    participants = [serialize_participant(row) for row in participant_rows]
    question_ids = normalize_question_ids(room.get('question_ids'))
    ranking = sorted(participants, key=participant_sort_key)
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
        'ranking': ranking,
        'server_time': to_api_iso(utc_now()),
        'started_at': to_api_iso(room.get('started_at')),
        'round_started_at': to_api_iso(room.get('round_started_at')),
        'finished_at': to_api_iso(room.get('finished_at')),
        'created_at': to_api_iso(room.get('created_at')),
        'updated_at': to_api_iso(room.get('updated_at')),
    }


def serialize_room(db: Session, room_id: int) -> dict:
    participants = tables.participants_table()
    room = dict(fetch_room_row(db, room_id))
    if advance_room_if_round_expired(db, room):
        room = dict(fetch_room_row(db, room_id))
    participant_rows = [
        dict(row)
        for row in db.execute(
            select(participants).where(
                participants.c.room_id == room_id,
                participants.c.status == PARTICIPANT_STATUS_JOINED,
            ).order_by(participants.c.joined_at.asc(), participants.c.id.asc())
        ).mappings().all()
    ]
    return serialize_room_snapshot(room, participant_rows)


def serialize_closed_room(
    db: Session,
    room: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    participants = tables.participants_table()
    participant_rows = [
        dict(row)
        for row in db.execute(
            select(participants).where(
                participants.c.room_id == int(room['id']),
                participants.c.status == PARTICIPANT_STATUS_JOINED,
            )
        ).mappings().all()
    ]
    serialized_room = serialize_room_snapshot({**room, 'status': 'closed'}, participant_rows)
    return {
        'status': 'closed',
        'room_id': int(room['id']),
        'reason': reason,
        'room': serialized_room,
        'server_time': to_api_iso(utc_now()),
    }

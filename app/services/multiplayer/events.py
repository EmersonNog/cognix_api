from typing import Any

from app.core.datetime_utils import to_api_iso, utc_now

EVENT_ROOM_SYNCED = 'room.synced'
EVENT_ROOM_JOINED = 'room.joined'
EVENT_ROOM_LEFT = 'room.left'
EVENT_ROOM_CLOSED = 'room.closed'
EVENT_MATCH_STARTED = 'match.started'
EVENT_ROUND_STARTED = 'round.started'
EVENT_ANSWER_SUBMITTED = 'answer.submitted'
EVENT_MATCH_FINISHED = 'match.finished'

MULTIPLAYER_EVENT_TYPES = (
    EVENT_ROOM_SYNCED,
    EVENT_ROOM_JOINED,
    EVENT_ROOM_LEFT,
    EVENT_ROOM_CLOSED,
    EVENT_MATCH_STARTED,
    EVENT_ROUND_STARTED,
    EVENT_ANSWER_SUBMITTED,
    EVENT_MATCH_FINISHED,
)


def build_room_event(
    event_type: str,
    room: dict[str, Any],
    *,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if event_type not in MULTIPLAYER_EVENT_TYPES:
        raise ValueError(f'Unsupported multiplayer event: {event_type}')

    payload = {
        'event': event_type,
        'room_id': int(room['id']),
        'server_time': to_api_iso(utc_now()),
        'room': room,
    }
    if data:
        payload['data'] = data
    return payload

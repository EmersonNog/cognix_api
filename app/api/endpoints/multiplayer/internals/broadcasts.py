import logging

from app.services.multiplayer import (
    EVENT_MATCH_FINISHED,
    EVENT_ROOM_SYNCED,
    EVENT_ROUND_STARTED,
    build_room_event,
    multiplayer_connection_manager,
)

logger = logging.getLogger(__name__)


async def broadcast_room_event(
    room_id: int,
    event_type: str,
    room_payload: dict,
    *,
    data: dict | None = None,
) -> None:
    await multiplayer_connection_manager.broadcast(
        room_id,
        build_room_event(event_type, room_payload, data=data),
    )


async def broadcast_transition_events(
    previous_room: dict | None,
    current_room: dict,
    *,
    primary_event: str,
    data: dict | None = None,
) -> None:
    room_id = int(current_room['id'])
    logger.info(
        'multiplayer_transition room_id=%s primary_event=%s previous_status=%s current_status=%s question_index=%s',
        room_id,
        primary_event,
        previous_room.get('status') if previous_room else None,
        current_room.get('status'),
        current_room.get('current_question_index'),
    )
    await broadcast_room_event(room_id, primary_event, current_room, data=data)
    await broadcast_room_event(room_id, EVENT_ROOM_SYNCED, current_room)

    if previous_room is None:
        return

    if (
        previous_room.get('status') != current_room.get('status')
        and current_room.get('status') == 'in_progress'
    ):
        await broadcast_room_event(room_id, EVENT_ROUND_STARTED, current_room)
        return

    if (
        previous_room.get('status') != current_room.get('status')
        and current_room.get('status') == 'finished'
    ):
        await broadcast_room_event(room_id, EVENT_MATCH_FINISHED, current_room)
        return

    if (
        previous_room.get('current_question_index')
        != current_room.get('current_question_index')
        and current_room.get('status') == 'in_progress'
    ):
        await broadcast_room_event(room_id, EVENT_ROUND_STARTED, current_room)

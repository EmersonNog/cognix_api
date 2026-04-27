from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.deps.entitlements import require_full_access
from app.api.endpoints.helpers import require_user_context
from app.db.session import SessionLocal
from app.services.multiplayer import (
    EVENT_ANSWER_SUBMITTED,
    EVENT_MATCH_STARTED,
    EVENT_ROOM_CLOSED,
    EVENT_ROOM_JOINED,
    EVENT_ROOM_LEFT,
    EVENT_ROOM_SYNCED,
    create_room,
    get_room_by_id,
    get_room_by_pin,
    join_room,
    leave_room,
    multiplayer_connection_manager,
    normalize_pin,
    parse_answer_payload,
    parse_create_room_payload,
    parse_join_room_payload,
    remove_participant,
    start_room,
    submit_answer,
)

from .internals import auth as multiplayer_auth
from .internals import broadcasts as multiplayer_broadcasts
from .internals import commands as multiplayer_commands
from .internals import host_timeout as multiplayer_host_timeout
from .internals import websocket as multiplayer_websocket
from .internals.constants import HOST_OFFLINE_GRACE_SECONDS

router = APIRouter()

# Backwards-compatible aliases for tests and internal diagnostics.
_authenticate_websocket = multiplayer_auth.authenticate_websocket
_broadcast_room_event = multiplayer_broadcasts.broadcast_room_event
_broadcast_transition_events = multiplayer_broadcasts.broadcast_transition_events
_display_name_from_claims = multiplayer_auth.display_name_from_claims
_execute_room_command = multiplayer_commands.execute_room_command
_handle_host_offline_timeout = multiplayer_host_timeout.handle_host_offline_timeout
_is_host_member = multiplayer_auth.is_host_member
_payload_with_display_name = multiplayer_auth.payload_with_display_name
_track_host_http_activity = multiplayer_host_timeout.track_host_http_activity


@router.post('/rooms', dependencies=[Depends(require_full_access)])
async def create_multiplayer_room(
    payload: dict | None = None,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    parsed_payload = parse_create_room_payload(
        multiplayer_auth.payload_with_display_name(payload, user_claims)
    )
    room = create_room(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        display_name=str(parsed_payload['display_name']),
        max_participants=int(parsed_payload['max_participants']),
    )
    await multiplayer_broadcasts.broadcast_transition_events(
        None,
        room,
        primary_event=EVENT_ROOM_SYNCED,
    )
    return room


@router.post('/rooms/join', dependencies=[Depends(require_full_access)])
async def join_multiplayer_room(
    payload: dict,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    parsed_payload = parse_join_room_payload(
        multiplayer_auth.payload_with_display_name(payload, user_claims)
    )
    previous_room = get_room_by_pin(db, str(parsed_payload['pin']))
    room = join_room(
        db,
        pin=str(parsed_payload['pin']),
        user_id=user_id,
        firebase_uid=firebase_uid,
        display_name=str(parsed_payload['display_name']),
    )
    await multiplayer_broadcasts.broadcast_transition_events(
        previous_room,
        room,
        primary_event=EVENT_ROOM_JOINED,
    )
    return room


@router.get('/rooms/pin/{pin}', dependencies=[Depends(require_full_access)])
def get_multiplayer_room_by_pin(
    pin: str,
    db: Session = Depends(get_db),
    _user_claims: dict = Depends(get_current_user),
) -> dict:
    return get_room_by_pin(db, normalize_pin(pin))


@router.get('/rooms/{room_id}', dependencies=[Depends(require_full_access)])
async def get_multiplayer_room(
    room_id: int,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    room = get_room_by_id(db, room_id)
    multiplayer_host_timeout.track_host_http_activity(room, user_claims=user_claims)
    return room


@router.delete(
    '/rooms/{room_id}/participants/{participant_id}',
    dependencies=[Depends(require_full_access)],
)
async def remove_multiplayer_participant(
    room_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    previous_room = get_room_by_id(db, room_id)
    user_id, _firebase_uid = require_user_context(user_claims)
    room = remove_participant(
        db,
        room_id=room_id,
        participant_id=participant_id,
        host_user_id=user_id,
    )
    await multiplayer_broadcasts.broadcast_transition_events(
        previous_room,
        room,
        primary_event=EVENT_ROOM_LEFT,
    )
    return room


@router.post('/rooms/{room_id}/leave', dependencies=[Depends(require_full_access)])
async def leave_multiplayer_room(
    room_id: int,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    previous_room = get_room_by_id(db, room_id)
    user_id, _firebase_uid = require_user_context(user_claims)
    payload = leave_room(db, room_id=room_id, user_id=user_id)
    if payload.get('status') == 'closed' and isinstance(payload.get('room'), dict):
        await multiplayer_broadcasts.broadcast_room_event(
            room_id,
            EVENT_ROOM_CLOSED,
            payload['room'],
            data={'reason': payload.get('reason')},
        )
        return payload

    await multiplayer_broadcasts.broadcast_transition_events(
        previous_room,
        payload,
        primary_event=EVENT_ROOM_LEFT,
    )
    return payload


@router.post('/rooms/{room_id}/start', dependencies=[Depends(require_full_access)])
async def start_multiplayer_room(
    room_id: int,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    previous_room = get_room_by_id(db, room_id)
    user_id, _firebase_uid = require_user_context(user_claims)
    room = start_room(db, room_id=room_id, host_user_id=user_id)
    await multiplayer_broadcasts.broadcast_transition_events(
        previous_room,
        room,
        primary_event=EVENT_MATCH_STARTED,
    )
    return room


@router.post('/rooms/{room_id}/answers', dependencies=[Depends(require_full_access)])
async def submit_multiplayer_answer(
    room_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    previous_room = get_room_by_id(db, room_id)
    user_id, _firebase_uid = require_user_context(user_claims)
    parsed_payload = parse_answer_payload(payload)
    result = submit_answer(
        db,
        room_id=room_id,
        user_id=user_id,
        question_id=int(parsed_payload['question_id']),
        selected_letter=str(parsed_payload['selected_letter']),
    )
    await multiplayer_broadcasts.broadcast_transition_events(
        previous_room,
        result['room'],
        primary_event=EVENT_ANSWER_SUBMITTED,
        data={
            'question_id': int(parsed_payload['question_id']),
            'selected_letter': str(parsed_payload['selected_letter']),
        },
    )
    return result


@router.websocket('/rooms/{room_id}/ws')
async def multiplayer_room_websocket(websocket: WebSocket, room_id: int) -> None:
    await multiplayer_websocket.multiplayer_room_websocket(websocket, room_id)


__all__ = [
    'HOST_OFFLINE_GRACE_SECONDS',
    'SessionLocal',
    'get_current_user',
    'get_room_by_id',
    'multiplayer_connection_manager',
    'router',
    'start_room',
]

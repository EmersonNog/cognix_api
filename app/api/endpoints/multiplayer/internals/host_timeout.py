from fastapi import HTTPException

from app.api.endpoints.helpers import require_user_context
from app.db.session import SessionLocal
from app.services.multiplayer import (
    EVENT_ROOM_CLOSED,
    close_room_for_host_disconnect,
    get_room_by_id,
    multiplayer_connection_manager,
)

from .auth import is_host_member
from .broadcasts import broadcast_room_event
from .constants import HOST_OFFLINE_GRACE_SECONDS


async def handle_host_offline_timeout(room_id: int, *, force: bool = False) -> None:
    if not force and multiplayer_connection_manager.has_host_connection(room_id):
        return

    db = SessionLocal()
    try:
        room = get_room_by_id(db, room_id)
        payload = close_room_for_host_disconnect(
            db,
            room_id=room_id,
            host_user_id=int(room['host_user_id']),
        )
    except HTTPException:
        return
    finally:
        db.close()

    if payload and payload.get('status') == 'closed' and isinstance(payload.get('room'), dict):
        await broadcast_room_event(
            room_id,
            EVENT_ROOM_CLOSED,
            payload['room'],
            data={'reason': payload.get('reason')},
        )


def track_host_http_activity(room: dict, *, user_claims: dict) -> None:
    try:
        user_id, firebase_uid = require_user_context(
            user_claims,
            require_firebase_uid=True,
        )
    except HTTPException:
        return

    if not is_host_member(room, user_id=user_id, firebase_uid=firebase_uid):
        return

    multiplayer_connection_manager.reset_host_timeout(
        int(room['id']),
        delay_seconds=HOST_OFFLINE_GRACE_SECONDS,
        callback=handle_host_offline_timeout,
        force=True,
    )

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect, status

from app.api.endpoints.helpers import require_user_context
from app.core.datetime_utils import to_api_iso, utc_now
from app.db.session import SessionLocal
from app.services.multiplayer import (
    EVENT_ROOM_SYNCED,
    build_room_event,
    get_room_by_id,
    multiplayer_connection_manager,
)

from .auth import authenticate_websocket, is_host_member
from .commands import execute_room_command
from .constants import HOST_OFFLINE_GRACE_SECONDS
from .host_timeout import handle_host_offline_timeout

logger = logging.getLogger(__name__)


async def multiplayer_room_websocket(websocket: WebSocket, room_id: int) -> None:
    token = websocket.query_params.get('token', '').strip()
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason='Missing token')
        return

    try:
        user_claims = authenticate_websocket(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason='Invalid token')
        return

    db = SessionLocal()
    host_timeout_handled = False
    try:
        user_id, firebase_uid = require_user_context(
            user_claims,
            require_firebase_uid=True,
        )
        logger.info(
            'multiplayer_ws_auth_ok room_id=%s user_id=%s firebase_uid=%s',
            room_id,
            user_id,
            firebase_uid,
        )
        room = get_room_by_id(db, room_id)
        is_member = any(
            int(participant.get('user_id') or 0) == user_id
            or participant.get('firebase_uid') == firebase_uid
            for participant in room.get('participants', [])
        )
        if not is_member:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason='Not a room participant',
            )
            return

        is_host = is_host_member(room, user_id=user_id, firebase_uid=firebase_uid)
        await multiplayer_connection_manager.connect(
            room_id,
            websocket,
            user_id=user_id,
            is_host=is_host,
        )
        await websocket.send_json(build_room_event(EVENT_ROOM_SYNCED, room))
        if is_host:
            multiplayer_connection_manager.reset_host_timeout(
                room_id,
                delay_seconds=HOST_OFFLINE_GRACE_SECONDS,
                callback=handle_host_offline_timeout,
                force=True,
            )

        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=HOST_OFFLINE_GRACE_SECONDS if is_host else None,
                )
            except asyncio.TimeoutError:
                logger.info(
                    'multiplayer_ws_host_idle_timeout room_id=%s user_id=%s',
                    room_id,
                    user_id,
                )
                host_timeout_handled = True
                await handle_host_offline_timeout(room_id, force=True)
                break

            if is_host:
                multiplayer_connection_manager.reset_host_timeout(
                    room_id,
                    delay_seconds=HOST_OFFLINE_GRACE_SECONDS,
                    callback=handle_host_offline_timeout,
                    force=True,
                )

            normalized = message.strip().lower()
            event_type = normalized
            payload = {}
            if normalized.startswith('{'):
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    payload = {}
                event_type = str(payload.get('type') or '').strip().lower()

            if event_type == 'ping':
                logger.debug('multiplayer_ws_ping room_id=%s user_id=%s', room_id, user_id)
                await websocket.send_json(
                    {
                        'event': 'pong',
                        'room_id': room_id,
                        'server_time': to_api_iso(utc_now()),
                    }
                )
                continue

            if event_type == 'command':
                request_id = str(payload.get('request_id') or '').strip()
                action = str(payload.get('action') or '').strip()
                command_payload = payload.get('payload')
                if not request_id or not action:
                    await websocket.send_json(
                        {
                            'event': 'command.error',
                            'request_id': request_id,
                            'action': action,
                            'message': 'Invalid multiplayer command.',
                            'status_code': 400,
                            'server_time': to_api_iso(utc_now()),
                        }
                    )
                    continue
                if not isinstance(command_payload, dict):
                    command_payload = {}
                await execute_room_command(
                    websocket=websocket,
                    db=db,
                    room_id=room_id,
                    user_id=user_id,
                    request_id=request_id,
                    action=action,
                    payload=command_payload,
                )
    except WebSocketDisconnect:
        logger.info('multiplayer_ws_client_disconnected room_id=%s', room_id)
    finally:
        metadata = multiplayer_connection_manager.disconnect(room_id, websocket)
        if (
            metadata.get('is_host')
            and not metadata.get('has_host_connection', False)
            and not host_timeout_handled
        ):
            multiplayer_connection_manager.schedule_host_timeout(
                room_id,
                delay_seconds=HOST_OFFLINE_GRACE_SECONDS,
                callback=handle_host_offline_timeout,
            )
        db.close()

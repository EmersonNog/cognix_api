import logging

from fastapi import HTTPException, WebSocket
from sqlalchemy.orm import Session

from app.core.datetime_utils import to_api_iso, utc_now
from app.services.multiplayer import (
    EVENT_ANSWER_SUBMITTED,
    EVENT_MATCH_STARTED,
    EVENT_ROOM_CLOSED,
    EVENT_ROOM_LEFT,
    get_room_by_id,
    leave_room,
    parse_answer_payload,
    remove_participant,
    start_room,
    submit_answer,
)

from .broadcasts import broadcast_room_event, broadcast_transition_events

logger = logging.getLogger(__name__)


async def send_command_result(
    websocket: WebSocket,
    *,
    request_id: str,
    action: str,
    result: dict,
) -> None:
    logger.info(
        'multiplayer_ws_command_result room_id=%s action=%s request_id=%s',
        result.get('id') or result.get('room_id'),
        action,
        request_id,
    )
    await websocket.send_json(
        {
            'event': 'command.result',
            'request_id': request_id,
            'action': action,
            'result': result,
            'server_time': to_api_iso(utc_now()),
        }
    )


async def send_command_error(
    websocket: WebSocket,
    *,
    request_id: str,
    action: str,
    error: HTTPException,
) -> None:
    logger.warning(
        'multiplayer_ws_command_error action=%s request_id=%s status_code=%s detail=%s',
        action,
        request_id,
        error.status_code,
        error.detail,
    )
    await websocket.send_json(
        {
            'event': 'command.error',
            'request_id': request_id,
            'action': action,
            'message': str(error.detail),
            'status_code': int(error.status_code),
            'server_time': to_api_iso(utc_now()),
        }
    )


async def execute_room_command(
    *,
    websocket: WebSocket,
    db: Session,
    room_id: int,
    user_id: int,
    request_id: str,
    action: str,
    payload: dict,
) -> None:
    previous_room = get_room_by_id(db, room_id)
    logger.info(
        'multiplayer_ws_command room_id=%s user_id=%s action=%s request_id=%s',
        room_id,
        user_id,
        action,
        request_id,
    )
    try:
        if action == 'start_match':
            result = start_room(db, room_id=room_id, host_user_id=user_id)
            await broadcast_transition_events(
                previous_room,
                result,
                primary_event=EVENT_MATCH_STARTED,
            )
        elif action == 'submit_answer':
            parsed_payload = parse_answer_payload(payload)
            result = submit_answer(
                db,
                room_id=room_id,
                user_id=user_id,
                question_id=int(parsed_payload['question_id']),
                selected_letter=str(parsed_payload['selected_letter']),
            )
            await broadcast_transition_events(
                previous_room,
                result['room'],
                primary_event=EVENT_ANSWER_SUBMITTED,
                data={
                    'question_id': int(parsed_payload['question_id']),
                    'selected_letter': str(parsed_payload['selected_letter']),
                },
            )
        elif action == 'leave_room':
            result = leave_room(db, room_id=room_id, user_id=user_id)
            if result.get('status') == 'closed' and isinstance(result.get('room'), dict):
                await broadcast_room_event(
                    room_id,
                    EVENT_ROOM_CLOSED,
                    result['room'],
                    data={'reason': result.get('reason')},
                )
            else:
                await broadcast_transition_events(
                    previous_room,
                    result,
                    primary_event=EVENT_ROOM_LEFT,
                )
        elif action == 'remove_participant':
            try:
                participant_id = int(str(payload.get('participant_id') or '').strip())
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail='participant_id must be numeric',
                ) from exc
            result = remove_participant(
                db,
                room_id=room_id,
                participant_id=participant_id,
                host_user_id=user_id,
            )
            await broadcast_transition_events(
                previous_room,
                result,
                primary_event=EVENT_ROOM_LEFT,
            )
        else:
            raise HTTPException(status_code=400, detail='Unsupported multiplayer command')
    except HTTPException as error:
        await send_command_error(
            websocket,
            request_id=request_id,
            action=action,
            error=error,
        )
        return

    await send_command_result(
        websocket,
        request_id=request_id,
        action=action,
        result=result,
    )

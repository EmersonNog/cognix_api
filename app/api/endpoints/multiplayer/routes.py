from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.endpoints.helpers import require_user_context
from app.services.multiplayer import (
    create_room,
    get_room_by_id,
    get_room_by_pin,
    join_room,
    leave_room,
    normalize_pin,
    parse_answer_payload,
    parse_create_room_payload,
    parse_join_room_payload,
    remove_participant,
    start_room,
    submit_answer,
)

router = APIRouter()


def _display_name_from_claims(user_claims: dict) -> str:
    internal_user = user_claims.get('internal_user') or {}
    value = internal_user.get('display_name') or user_claims.get('name')
    if not value:
        value = user_claims.get('email') or 'Jogador'
    return str(value).strip()[:255] or 'Jogador'


def _payload_with_display_name(payload: dict | None, user_claims: dict) -> dict:
    data = dict(payload or {})
    data['display_name'] = data.get('display_name') or _display_name_from_claims(
        user_claims
    )
    return data


@router.post('/rooms')
def create_multiplayer_room(
    payload: dict | None = None,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    parsed_payload = parse_create_room_payload(
        _payload_with_display_name(payload, user_claims)
    )
    return create_room(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        display_name=str(parsed_payload['display_name']),
        max_participants=int(parsed_payload['max_participants']),
    )


@router.post('/rooms/join')
def join_multiplayer_room(
    payload: dict,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    parsed_payload = parse_join_room_payload(
        _payload_with_display_name(payload, user_claims)
    )
    return join_room(
        db,
        pin=str(parsed_payload['pin']),
        user_id=user_id,
        firebase_uid=firebase_uid,
        display_name=str(parsed_payload['display_name']),
    )


@router.get('/rooms/pin/{pin}')
def get_multiplayer_room_by_pin(
    pin: str,
    db: Session = Depends(get_db),
    _user_claims: dict = Depends(get_current_user),
) -> dict:
    return get_room_by_pin(db, normalize_pin(pin))


@router.get('/rooms/{room_id}')
def get_multiplayer_room(
    room_id: int,
    db: Session = Depends(get_db),
    _user_claims: dict = Depends(get_current_user),
) -> dict:
    return get_room_by_id(db, room_id)


@router.delete('/rooms/{room_id}/participants/{participant_id}')
def remove_multiplayer_participant(
    room_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _firebase_uid = require_user_context(user_claims)
    return remove_participant(
        db,
        room_id=room_id,
        participant_id=participant_id,
        host_user_id=user_id,
    )


@router.post('/rooms/{room_id}/leave')
def leave_multiplayer_room(
    room_id: int,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _firebase_uid = require_user_context(user_claims)
    return leave_room(db, room_id=room_id, user_id=user_id)


@router.post('/rooms/{room_id}/start')
def start_multiplayer_room(
    room_id: int,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _firebase_uid = require_user_context(user_claims)
    return start_room(db, room_id=room_id, host_user_id=user_id)


@router.post('/rooms/{room_id}/answers')
def submit_multiplayer_answer(
    room_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _firebase_uid = require_user_context(user_claims)
    parsed_payload = parse_answer_payload(payload)
    return submit_answer(
        db,
        room_id=room_id,
        user_id=user_id,
        question_id=int(parsed_payload['question_id']),
        selected_letter=str(parsed_payload['selected_letter']),
    )

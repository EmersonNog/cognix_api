from fastapi import HTTPException

DEFAULT_MAX_PARTICIPANTS = 8
MIN_PARTICIPANTS = 2
MAX_PARTICIPANTS = 8


def normalize_pin(value: object) -> str:
    pin = str(value or '').strip()
    if not pin:
        raise HTTPException(status_code=400, detail='pin is required')
    if len(pin) != 6 or not pin.isdigit():
        raise HTTPException(status_code=400, detail='pin must have 6 digits')
    return pin


def normalize_display_name(value: object, fallback: str = 'Jogador') -> str:
    display_name = str(value or fallback).strip()
    if not display_name:
        display_name = fallback
    return display_name[:255]


def parse_max_participants(value: object) -> int:
    if value is None:
        return DEFAULT_MAX_PARTICIPANTS
    try:
        max_participants = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail='max_participants must be numeric',
        ) from exc
    if max_participants < MIN_PARTICIPANTS or max_participants > MAX_PARTICIPANTS:
        raise HTTPException(
            status_code=400,
            detail=f'max_participants must be between {MIN_PARTICIPANTS} and {MAX_PARTICIPANTS}',
        )
    return max_participants


def parse_create_room_payload(payload: object) -> dict[str, object]:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail='Invalid room payload')

    return {
        'display_name': normalize_display_name(payload.get('display_name')),
        'max_participants': parse_max_participants(payload.get('max_participants')),
    }


def parse_join_room_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail='Invalid join payload')

    return {
        'pin': normalize_pin(payload.get('pin')),
        'display_name': normalize_display_name(payload.get('display_name')),
    }

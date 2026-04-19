from fastapi import HTTPException

from app.api.deps.users import sync_internal_user
from app.api.endpoints.helpers import require_user_context
from app.core.security import verify_firebase_token
from app.db.session import SessionLocal


def display_name_from_claims(user_claims: dict) -> str:
    internal_user = user_claims.get('internal_user') or {}
    value = internal_user.get('display_name') or user_claims.get('name')
    if not value:
        value = user_claims.get('email') or 'Jogador'
    return str(value).strip()[:255] or 'Jogador'


def payload_with_display_name(payload: dict | None, user_claims: dict) -> dict:
    data = dict(payload or {})
    data['display_name'] = data.get('display_name') or display_name_from_claims(
        user_claims
    )
    return data


def authenticate_websocket(token: str) -> dict:
    db = SessionLocal()
    try:
        claims = verify_firebase_token(token)
        return sync_internal_user(db, claims)
    finally:
        db.close()


def is_host_member(room: dict, *, user_id: int, firebase_uid: str) -> bool:
    host_user_id = room.get('host_user_id')
    if host_user_id is not None:
        try:
            return int(host_user_id) == user_id
        except (TypeError, ValueError):
            pass

    host_firebase_uid = str(room.get('host_firebase_uid') or '').strip()
    if host_firebase_uid:
        return host_firebase_uid == firebase_uid

    for participant in room.get('participants', []):
        if not isinstance(participant, dict):
            continue
        participant_role = str(participant.get('role') or '').strip().lower()
        participant_user_id = participant.get('user_id')
        participant_firebase_uid = str(participant.get('firebase_uid') or '').strip()
        if participant_role == 'host' and (
            participant_firebase_uid == firebase_uid
            or participant_user_id == user_id
        ):
            return True
    return False


def host_context_from_claims(user_claims: dict) -> tuple[int, str] | None:
    try:
        return require_user_context(user_claims, require_firebase_uid=True)
    except HTTPException:
        return None

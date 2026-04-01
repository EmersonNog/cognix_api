from fastapi import HTTPException


def require_authenticated_user(user_claims: dict) -> tuple[int, str]:
    internal = user_claims.get('internal_user') or {}
    user_id = internal.get('id')
    firebase_uid = user_claims.get('uid')
    if not user_id or not firebase_uid:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return user_id, firebase_uid


def require_user_id(user_claims: dict) -> int:
    internal = user_claims.get('internal_user') or {}
    user_id = internal.get('id')
    if not user_id:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return user_id

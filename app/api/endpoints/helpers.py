from collections.abc import Mapping
from typing import Any, Literal, overload

from fastapi import HTTPException

from app.core.datetime_utils import utc_now

RECENT_AUTH_MAX_AGE_SECONDS = 300


@overload
def require_user_context(
    user_claims: Mapping[str, Any],
    *,
    require_firebase_uid: Literal[True],
) -> tuple[int, str]: ...


@overload
def require_user_context(
    user_claims: Mapping[str, Any],
    *,
    require_firebase_uid: Literal[False] = False,
) -> tuple[int, str | None]: ...


def require_user_context(
    user_claims: Mapping[str, Any],
    *,
    require_firebase_uid: bool = False,
) -> tuple[int, str | None]:
    internal_user = user_claims.get('internal_user') or {}
    user_id = internal_user.get('id')
    firebase_uid = user_claims.get('uid')

    if not user_id or (require_firebase_uid and not firebase_uid):
        raise HTTPException(status_code=401, detail='Unauthorized')

    return int(user_id), str(firebase_uid) if firebase_uid else None


def require_recent_authentication(
    user_claims: Mapping[str, Any],
    *,
    max_age_seconds: int = RECENT_AUTH_MAX_AGE_SECONDS,
) -> None:
    auth_time = user_claims.get('auth_time')
    if auth_time is None:
        raise HTTPException(status_code=403, detail='Recent authentication required')

    try:
        auth_time_seconds = int(auth_time)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=403,
            detail='Recent authentication required',
        ) from exc

    age_seconds = int(utc_now().timestamp()) - auth_time_seconds
    if age_seconds > max_age_seconds:
        raise HTTPException(status_code=403, detail='Recent authentication required')


def normalize_required_text(field_name: str, value: object) -> str:
    normalized = str(value or '').strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f'{field_name} is required')
    return normalized

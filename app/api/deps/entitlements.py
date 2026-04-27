from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.endpoints.helpers import require_user_context
from app.services.entitlements.status.current import get_current_access_status

from .auth import get_current_user
from .db import get_db

PREMIUM_ACCESS_DENIED_DETAIL = {
    'code': 'subscription_required',
    'message': 'Continue de onde parou com a Experiência Cognix 🚀 Desbloqueie recursos avançados em segundos.'
}

def get_access_status_for_claims(
    db: Session,
    user_claims: dict,
) -> dict[str, object]:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    return get_current_access_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=_current_user_email(user_claims),
    )

def require_full_access(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    access_status = get_access_status_for_claims(db, user_claims)

    if access_status.get('hasFullAccess') is not True:
        raise HTTPException(
            status_code=403,
            detail=PREMIUM_ACCESS_DENIED_DETAIL,
        )

    return access_status

def ensure_full_access_for_claims(db: Session, user_claims: dict) -> dict[str, object]:
    access_status = get_access_status_for_claims(db, user_claims)

    if access_status.get('hasFullAccess') is not True:
        raise HTTPException(
            status_code=403,
            detail=PREMIUM_ACCESS_DENIED_DETAIL,
        )

    return access_status

def _current_user_email(user_claims: dict) -> str | None:
    internal_user = user_claims.get('internal_user') or {}
    return user_claims.get('email') or internal_user.get('email')
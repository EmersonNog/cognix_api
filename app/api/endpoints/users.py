from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.services.profile_score import fetch_profile_score

router = APIRouter()


def _require_user_id(user_claims: dict) -> int:
    internal_user = user_claims.get('internal_user') or {}
    user_id = internal_user.get('id')
    if not user_id:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return int(user_id)


@router.post('/sync')
def sync_user(user_claims: dict = Depends(get_current_user)) -> dict:
    internal_user = user_claims.get('internal_user')
    return {
        'status': 'ok',
        'uid': user_claims.get('uid'),
        'internal_user': internal_user,
    }


@router.get('/profile')
def get_profile(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id = _require_user_id(user_claims)
    payload = fetch_profile_score(db, user_id)
    payload['uid'] = user_claims.get('uid')
    return payload

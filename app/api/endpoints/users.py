from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.services.economy import fetch_user_economy_state, select_profile_avatar
from app.services.profile_score import fetch_profile_score
from app.services.recommendations import fetch_home_recommendations

router = APIRouter()

def _require_user_id(user_claims: dict) -> int:
    internal_user = user_claims.get('internal_user') or {}
    user_id = internal_user.get('id')
    if not user_id:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return int(user_id)

def _require_authenticated_user(user_claims: dict) -> tuple[int, str]:
    user_id = _require_user_id(user_claims)
    firebase_uid = user_claims.get('uid')
    if not firebase_uid:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return user_id, str(firebase_uid)

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
    user_id, firebase_uid = _require_authenticated_user(user_claims)
    payload = fetch_profile_score(db, user_id)
    payload.update(
        fetch_user_economy_state(
            db,
            user_id=user_id,
            firebase_uid=firebase_uid,
        )
    )
    payload['uid'] = user_claims.get('uid')
    db.commit()
    return payload

@router.get('/recommendations')
def get_recommendations(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id = _require_user_id(user_claims)
    payload = fetch_home_recommendations(db, user_id=user_id)
    db.commit()
    return payload

@router.post('/avatar/select')
def select_avatar(
    payload: dict,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = _require_authenticated_user(user_claims)
    avatar_seed = str(payload.get('avatar_seed') or '').strip()
    if not avatar_seed:
        raise HTTPException(status_code=400, detail='avatar_seed is required')

    result = select_profile_avatar(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        avatar_seed=avatar_seed,
    )
    if result.get('status') == 'invalid_avatar':
        raise HTTPException(status_code=400, detail='invalid avatar_seed')

    db.commit()
    return result
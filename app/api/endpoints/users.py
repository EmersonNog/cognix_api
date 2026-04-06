from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.endpoints.helpers import (
    normalize_required_text,
    require_recent_authentication,
    require_user_context,
)
from app.services.economy import fetch_user_economy_state, select_profile_avatar
from app.services.account import delete_user_account
from app.services.profile_score import fetch_profile_score
from app.services.recommendations import fetch_home_recommendations

router = APIRouter()

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
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    payload = fetch_profile_score(db, user_id)
    payload.update(
        fetch_user_economy_state(
            db,
            user_id=user_id,
            firebase_uid=firebase_uid,
        )
    )
    payload['uid'] = firebase_uid
    db.commit()
    return payload

@router.get('/recommendations')
def get_recommendations(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, _ = require_user_context(user_claims)
    payload = fetch_home_recommendations(db, user_id=user_id)
    db.commit()
    return payload

@router.post('/avatar/select')
def select_avatar(
    payload: dict,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    avatar_seed = normalize_required_text('avatar_seed', payload.get('avatar_seed'))

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


@router.delete('/account')
def delete_account(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    require_recent_authentication(user_claims)
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
    return delete_user_account(db, user_id=user_id, firebase_uid=firebase_uid)

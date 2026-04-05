from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.services.study_plan import (
    fetch_study_plan,
    preview_study_plan,
    save_study_plan,
)

router = APIRouter()

def _require_authenticated_user(user_claims: dict) -> tuple[int, str]:
    internal_user = user_claims.get('internal_user') or {}
    user_id = internal_user.get('id')
    firebase_uid = user_claims.get('uid')
    if not user_id or not firebase_uid:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return int(user_id), str(firebase_uid)

@router.get('')
def get_user_study_plan(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, _firebase_uid = _require_authenticated_user(user_claims)
    payload = fetch_study_plan(db, user_id=user_id)
    db.commit()
    return payload

@router.post('')
def save_user_study_plan(
    payload: dict[str, object],
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, firebase_uid = _require_authenticated_user(user_claims)
    result = save_study_plan(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        payload=payload,
    )
    db.commit()
    return result


@router.post('/preview')
def preview_user_study_plan(
    payload: dict[str, object],
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, _firebase_uid = _require_authenticated_user(user_claims)
    result = preview_study_plan(
        db,
        user_id=user_id,
        payload=payload,
    )
    db.commit()
    return result

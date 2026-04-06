from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.endpoints.helpers import require_user_context
from app.services.study_plan import (
    fetch_study_plan,
    preview_study_plan,
    save_study_plan,
)

router = APIRouter()

@router.get('')
def get_user_study_plan(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, _firebase_uid = require_user_context(user_claims)
    payload = fetch_study_plan(db, user_id=user_id)
    db.commit()
    return payload

@router.post('')
def save_user_study_plan(
    payload: dict[str, object],
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )
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
    user_id, _firebase_uid = require_user_context(user_claims)
    result = preview_study_plan(
        db,
        user_id=user_id,
        payload=payload,
    )
    db.commit()
    return result

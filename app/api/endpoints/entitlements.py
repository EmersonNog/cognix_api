from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.endpoints.helpers import (
    current_user_email as _current_user_email,
    require_user_context,
)
from app.services.entitlements.status.current import get_current_access_status
from app.services.entitlements.trials.service import start_trial

router = APIRouter()


@router.get('/current')
def get_current_entitlements(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
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


@router.post('/trial/start')
def start_trial_entitlement(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )

    return start_trial(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=_current_user_email(user_claims),
    )

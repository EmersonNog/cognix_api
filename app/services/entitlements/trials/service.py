from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now

from ..access.policies import TRIAL_GRANT_TYPE, trial_duration
from ..grants.records import create_user_grant
from ..status.current import get_current_access_status

def start_trial(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    email: str | None,
) -> dict[str, object]:
    current = get_current_access_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
    )

    if current['hasFullAccess'] is True or current['trialAvailable'] is not True:
        return current

    starts_at = utc_now()
    ends_at = starts_at + trial_duration()

    try:
        create_user_grant(
            db,
            user_id=user_id,
            firebase_uid=firebase_uid,
            grant_type=TRIAL_GRANT_TYPE,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        db.commit()
    except IntegrityError:
        db.rollback()

    return get_current_access_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
    )

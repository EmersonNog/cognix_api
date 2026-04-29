from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.datetime_utils import ensure_utc, to_api_iso
from app.services.entitlements.access.policies import TRIAL_GRANT_TYPE


GrantFinder = Callable[..., dict[str, Any] | None]
GrantMarker = Callable[..., None]
Clock = Callable[[], datetime]


def get_current_trial_status(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    find_grant: GrantFinder,
    mark_expired: GrantMarker,
    now: Clock,
) -> dict[str, object]:
    grant = find_grant(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        grant_type=TRIAL_GRANT_TYPE,
    )

    if grant is None:
        return {
            'status': 'not_started',
            'isActive': False,
            'isAvailable': True,
            'startedAt': None,
            'endsAt': None,
        }

    status = str(grant.get('status') or 'expired')
    starts_at = _grant_datetime(grant.get('starts_at'))
    ends_at = _grant_datetime(grant.get('ends_at'))
    is_active = status == 'active' and ends_at is not None and ends_at > now()

    if status == 'active' and not is_active:
        mark_expired(db, grant_id=int(grant['id']))
        db.commit()
        status = 'expired'

    return {
        'status': status,
        'isActive': is_active,
        'isAvailable': False,
        'startedAt': to_api_iso(starts_at),
        'endsAt': to_api_iso(ends_at),
    }


def _grant_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return ensure_utc(value)

    return None

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.datetime_utils import ensure_utc, to_api_iso, utc_now
from app.services.payments.abacatepay.subscriptions.current import (
    get_current_subscription_status,
)

from ..access.policies import TRIAL_GRANT_TYPE, full_access_features
from ..grants.records import find_user_grant, mark_user_grant_expired

def get_current_access_status(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
) -> dict[str, object]:
    subscription = get_current_subscription_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
    )
    trial = _current_trial_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
    )

    if subscription.get('hasAccess') is True:
        return _response(
            access_status='subscription',
            has_full_access=True,
            active_source='subscription',
            subscription=subscription,
            trial=trial,
        )

    if trial['isActive']:
        return _response(
            access_status='trial',
            has_full_access=True,
            active_source='trial',
            subscription=subscription,
            trial=trial,
        )

    access_status = 'trial_available' if trial['isAvailable'] else 'trial_expired'
    return _response(
        access_status=access_status,
        has_full_access=False,
        active_source=None,
        subscription=subscription,
        trial=trial,
    )

def _current_trial_status(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
) -> dict[str, object]:
    grant = find_user_grant(
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
    is_active = status == 'active' and ends_at is not None and ends_at > utc_now()

    if status == 'active' and not is_active:
        mark_user_grant_expired(db, grant_id=int(grant['id']))
        db.commit()
        status = 'expired'

    return {
        'status': status,
        'isActive': is_active,
        'isAvailable': False,
        'startedAt': to_api_iso(starts_at),
        'endsAt': to_api_iso(ends_at),
    }


def _response(
    *,
    access_status: str,
    has_full_access: bool,
    active_source: str | None,
    subscription: dict,
    trial: dict[str, object],
) -> dict[str, object]:
    return {
        'accessStatus': access_status,
        'hasFullAccess': has_full_access,
        'activeSource': active_source,
        'features': full_access_features() if has_full_access else [],
        'trialAvailable': bool(trial['isAvailable']) and not has_full_access,
        'trialStatus': trial['status'],
        'trialStartedAt': trial['startedAt'],
        'trialEndsAt': trial['endsAt'],
        'subscriptionStatus': subscription.get('status'),
        'subscriptionPlanId': subscription.get('planId'),
        'subscriptionHasAccess': subscription.get('hasAccess') is True,
        'subscriptionAccessEndsAt': subscription.get('accessEndsAt'),
        'subscriptionWillCancelAtPeriodEnd': subscription.get(
            'willCancelAtPeriodEnd'
        )
        is True,
        'subscriptionCanCancel': subscription.get('canCancel') is True,
    }


def _grant_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return ensure_utc(value)

    return None

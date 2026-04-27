from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.datetime_utils import to_api_iso

from ..identity import hash_email
from ..persistence.records import find_current_subscription_for_user
from .access import current_period_ends_at, has_access
from .linking import link_subscription_if_needed


def get_current_subscription_status(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
) -> dict:
    email_hash = hash_email(email)
    subscription = find_current_subscription_for_user(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email_hash=email_hash,
    )

    if not subscription:
        return {
            'status': 'none',
            'canCancel': False,
            'hasAccess': False,
            'accessEndsAt': None,
            'willCancelAtPeriodEnd': False,
        }

    link_subscription_if_needed(
        db,
        subscription=subscription,
        user_id=user_id,
        firebase_uid=firebase_uid,
    )
    db.commit()

    status = str(subscription.get('status') or 'none')
    period_ends_at = current_period_ends_at(subscription)
    subscription_has_access = has_access(
        status=status,
        current_period_ends_at=period_ends_at,
    )
    return {
        'status': status,
        'planId': subscription.get('plan_id'),
        'hasAccess': subscription_has_access,
        'accessEndsAt': to_api_iso(period_ends_at),
        'willCancelAtPeriodEnd': status == 'cancelled' and subscription_has_access,
        'canCancel': status == 'active'
        and bool(subscription.get('external_subscription_id')),
    }

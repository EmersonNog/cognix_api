from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.datetime_utils import to_api_iso

from ...gateway.cancellations import cancel_subscription
from ..identity import hash_email
from ..persistence.records import (
    find_cancelable_subscription_for_user,
    mark_subscription_cancelled,
)
from .access import ensure_period_end, has_access
from .linking import link_subscription_if_needed


def cancel_current_subscription(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
) -> dict[str, object]:
    email_hash = hash_email(email)
    subscription = find_cancelable_subscription_for_user(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email_hash=email_hash,
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail='Nenhuma assinatura ativa encontrada.',
        )

    external_subscription_id = subscription.get('external_subscription_id')
    if not isinstance(external_subscription_id, str) or not external_subscription_id:
        raise HTTPException(
            status_code=409,
            detail='Assinatura ainda não esta pronta para cancelamento.',
        )

    cancel_subscription(external_subscription_id)
    period_ends_at = ensure_period_end(subscription)
    link_subscription_if_needed(
        db,
        subscription=subscription,
        user_id=user_id,
        firebase_uid=firebase_uid,
    )
    mark_subscription_cancelled(
        db,
        subscription_id=int(subscription['id']),
        current_period_ends_at=period_ends_at,
    )
    db.commit()

    return {
        'status': 'cancelled',
        'hasAccess': has_access(
            status='cancelled',
            current_period_ends_at=period_ends_at,
        ),
        'accessEndsAt': to_api_iso(period_ends_at),
    }

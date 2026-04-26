from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.datetime_utils import ensure_utc, to_api_iso, utc_now

from ..coupons.identifiers import hash_identifier
from ..gateway.cancellations import cancel_subscription
from .periods import parse_api_datetime, resolve_period_end
from .records import (
    find_cancelable_subscription_for_user,
    find_current_subscription_for_user,
    link_subscription_to_user,
    mark_subscription_cancelled,
)


def get_current_subscription_status(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
) -> dict:
    email_hash = _hash_email(email)
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

    _link_if_needed(
        db,
        subscription=subscription,
        user_id=user_id,
        firebase_uid=firebase_uid,
    )
    db.commit()

    status = str(subscription.get('status') or 'none')
    current_period_ends_at = _current_period_ends_at(subscription)
    has_access = _has_access(
        status=status,
        current_period_ends_at=current_period_ends_at,
    )
    return {
        'status': status,
        'planId': subscription.get('plan_id'),
        'hasAccess': has_access,
        'accessEndsAt': to_api_iso(current_period_ends_at),
        'willCancelAtPeriodEnd': status == 'cancelled' and has_access,
        'canCancel': status == 'active'
        and bool(subscription.get('external_subscription_id')),
    }


def cancel_current_subscription(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
) -> dict[str, object]:
    email_hash = _hash_email(email)
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
            detail='Assinatura ainda nao esta pronta para cancelamento.',
        )

    cancel_subscription(external_subscription_id)
    current_period_ends_at = _ensure_period_end(subscription)
    _link_if_needed(
        db,
        subscription=subscription,
        user_id=user_id,
        firebase_uid=firebase_uid,
    )
    mark_subscription_cancelled(
        db,
        subscription_id=int(subscription['id']),
        current_period_ends_at=current_period_ends_at,
    )
    db.commit()

    return {
        'status': 'cancelled',
        'hasAccess': _has_access(
            status='cancelled',
            current_period_ends_at=current_period_ends_at,
        ),
        'accessEndsAt': to_api_iso(current_period_ends_at),
    }


def _hash_email(email: str | None) -> str | None:
    normalized_email = str(email or '').strip().lower()
    return hash_identifier(normalized_email) if normalized_email else None


def _link_if_needed(
    db: Session,
    *,
    subscription: dict,
    user_id: int,
    firebase_uid: str | None,
) -> None:
    if subscription.get('user_id') == user_id and (
        not firebase_uid or subscription.get('firebase_uid') == firebase_uid
    ):
        return

    link_subscription_to_user(
        db,
        subscription_id=int(subscription['id']),
        user_id=user_id,
        firebase_uid=firebase_uid,
    )


def _current_period_ends_at(subscription: dict) -> datetime | None:
    return _subscription_datetime(subscription.get('current_period_ends_at'))


def _ensure_period_end(subscription: dict) -> datetime:
    current_period_ends_at = _current_period_ends_at(subscription)
    if current_period_ends_at is not None:
        return current_period_ends_at

    started_at = _subscription_datetime(
        subscription.get('updated_at')
    ) or _subscription_datetime(subscription.get('created_at'))
    return resolve_period_end(
        plan_id=str(subscription.get('plan_id') or ''),
        period_started_at=started_at,
    )


def _has_access(*, status: str, current_period_ends_at: datetime | None) -> bool:
    if status == 'active':
        return True

    if status != 'cancelled' or current_period_ends_at is None:
        return False

    return current_period_ends_at > utc_now()


def _subscription_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return ensure_utc(value)

    return parse_api_datetime(value)

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..coupons.identifiers import hash_identifier
from .records import (
    find_cancelable_subscription_for_user,
    find_current_subscription_for_user,
    link_subscription_to_user,
    mark_subscription_cancelled,
)
from ..gateway.cancellations import cancel_subscription


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
        return {'status': 'none', 'canCancel': False}

    _link_if_needed(
        db,
        subscription=subscription,
        user_id=user_id,
        firebase_uid=firebase_uid,
    )
    db.commit()

    status = str(subscription.get('status') or 'none')
    return {
        'status': status,
        'planId': subscription.get('plan_id'),
        'canCancel': status == 'active'
        and bool(subscription.get('external_subscription_id')),
    }


def cancel_current_subscription(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
) -> dict[str, str]:
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
    _link_if_needed(
        db,
        subscription=subscription,
        user_id=user_id,
        firebase_uid=firebase_uid,
    )
    mark_subscription_cancelled(db, subscription_id=int(subscription['id']))
    db.commit()

    return {'status': 'cancelled'}


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

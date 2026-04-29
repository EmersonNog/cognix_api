from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.datetime_utils import ensure_utc, to_api_iso, utc_now
from app.services.payments.abacatepay.subscriptions.identity import hash_email

from .records import find_current_google_play_subscription_for_user
from .verification import verify_google_play_subscription_purchase


@dataclass(frozen=True)
class _GooglePlaySubscriptionRefreshRequest:
    firebase_uid: str
    package_name: str
    product_id: str
    purchase_token: str


def get_current_google_play_subscription_status(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
) -> dict:
    email_hash = hash_email(email)
    subscription = find_current_google_play_subscription_for_user(
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

    subscription = _refresh_subscription_snapshot(
        db,
        subscription=subscription,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
        email_hash=email_hash,
    )

    return _serialize_status(subscription)


def _refresh_subscription_snapshot(
    db: Session,
    *,
    subscription: dict,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
    email_hash: str | None,
) -> dict:
    refresh_request = _refresh_request_from_subscription(
        subscription,
        fallback_firebase_uid=firebase_uid,
    )
    if refresh_request is None:
        return subscription

    try:
        verify_google_play_subscription_purchase(
            db,
            user_id=user_id,
            firebase_uid=refresh_request.firebase_uid,
            email=email,
            package_name=refresh_request.package_name,
            product_id=refresh_request.product_id,
            purchase_token=refresh_request.purchase_token,
        )
    except HTTPException:
        return subscription

    refreshed = find_current_google_play_subscription_for_user(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email_hash=email_hash,
    )

    return refreshed or subscription


def _refresh_request_from_subscription(
    subscription: dict,
    *,
    fallback_firebase_uid: str | None,
) -> _GooglePlaySubscriptionRefreshRequest | None:
    firebase_uid = str(
        subscription.get('firebase_uid') or fallback_firebase_uid or ''
    ).strip()
    package_name = str(subscription.get('package_name') or '').strip()
    product_id = str(subscription.get('product_id') or '').strip()
    purchase_token = str(subscription.get('purchase_token') or '').strip()

    if (
        not firebase_uid
        or not package_name
        or not product_id
        or not purchase_token
    ):
        return None

    return _GooglePlaySubscriptionRefreshRequest(
        firebase_uid=firebase_uid,
        package_name=package_name,
        product_id=product_id,
        purchase_token=purchase_token,
    )


def _serialize_status(subscription: dict) -> dict:
    status = str(subscription.get('status') or 'none')
    period_ends_at = ensure_utc(subscription.get('current_period_ends_at'))
    has_access = _has_access(status=status, current_period_ends_at=period_ends_at)

    return {
        'status': status,
        'provider': 'google_play',
        'planId': subscription.get('product_id'),
        'hasAccess': has_access,
        'accessEndsAt': to_api_iso(period_ends_at),
        'willCancelAtPeriodEnd': status == 'cancelled' and has_access,
        'canCancel': status == 'active',
    }


def _has_access(*, status: str, current_period_ends_at) -> bool:
    if status == 'active':
        return True

    if status != 'cancelled' or current_period_ends_at is None:
        return False

    return current_period_ends_at > utc_now()

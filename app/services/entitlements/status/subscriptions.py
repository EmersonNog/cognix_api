from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.datetime_utils import ensure_utc


SubscriptionStatusGetter = Callable[..., dict]
EmailHasher = Callable[[str | None], str | None]
IntroOfferLookup = Callable[..., bool]
Clock = Callable[[], datetime]


def get_current_subscription_status(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
    google_subscription_status_getter: SubscriptionStatusGetter,
    abacatepay_subscription_status_getter: SubscriptionStatusGetter,
    now: Clock,
) -> dict:
    subscriptions = [
        google_subscription_status_getter(
            db,
            user_id=user_id,
            firebase_uid=firebase_uid,
            email=email,
        ),
        abacatepay_subscription_status_getter(
            db,
            user_id=user_id,
            firebase_uid=firebase_uid,
            email=email,
        ),
    ]

    return _best_subscription_status(subscriptions, now=now)


def monthly_intro_offer_eligible(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
    hash_user_email: EmailHasher,
    has_used_intro_offer: IntroOfferLookup,
) -> bool:
    return not has_used_intro_offer(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email_hash=hash_user_email(email),
    )


def _best_subscription_status(subscriptions: list[dict], *, now: Clock) -> dict:
    with_access = [
        subscription
        for subscription in subscriptions
        if subscription.get('hasAccess') is True
    ]
    if with_access:
        return max(
            with_access,
            key=lambda subscription: _subscription_sort_key(
                subscription,
                now=now,
            ),
        )

    non_empty = [
        subscription
        for subscription in subscriptions
        if subscription.get('status') != 'none'
    ]
    if non_empty:
        return max(
            non_empty,
            key=lambda subscription: _subscription_sort_key(
                subscription,
                now=now,
            ),
        )

    return subscriptions[-1]


def _subscription_sort_key(
    subscription: dict,
    *,
    now: Clock,
) -> tuple[int, datetime]:
    status = str(subscription.get('status') or 'none')
    access_ends_at = _parse_access_ends_at(subscription.get('accessEndsAt'))
    priority = 2 if status == 'active' else 1 if status == 'cancelled' else 0
    return priority, access_ends_at or datetime.min.replace(tzinfo=now().tzinfo)


def _parse_access_ends_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return ensure_utc(datetime.fromisoformat(value.replace('Z', '+00:00')))
    except ValueError:
        return None

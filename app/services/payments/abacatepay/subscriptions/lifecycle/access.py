from __future__ import annotations

from datetime import datetime

from app.core.datetime_utils import ensure_utc, utc_now

from ..periods import parse_api_datetime, resolve_period_end


def current_period_ends_at(subscription: dict) -> datetime | None:
    return subscription_datetime(subscription.get('current_period_ends_at'))


def ensure_period_end(subscription: dict) -> datetime:
    period_ends_at = current_period_ends_at(subscription)
    if period_ends_at is not None:
        return period_ends_at

    started_at = subscription_datetime(
        subscription.get('updated_at')
    ) or subscription_datetime(subscription.get('created_at'))
    return resolve_period_end(
        plan_id=str(subscription.get('plan_id') or ''),
        period_started_at=started_at,
    )


def has_access(*, status: str, current_period_ends_at: datetime | None) -> bool:
    if status == 'active':
        return True

    if status != 'cancelled' or current_period_ends_at is None:
        return False

    return current_period_ends_at > utc_now()


def subscription_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return ensure_utc(value)

    return parse_api_datetime(value)

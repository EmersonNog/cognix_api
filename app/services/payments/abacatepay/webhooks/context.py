from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..shared.external_ids import parse_plan_id
from ..subscriptions.periods import parse_api_datetime, resolve_period_end


@dataclass(frozen=True)
class WebhookContext:
    external_id: str
    external_subscription_id: str | None
    checkout_id: str | None
    checkout_url: str | None
    current_period_ends_at: datetime


def build_webhook_context(payload: dict) -> WebhookContext | None:
    data = _as_dict(payload.get('data'))
    checkout = _as_dict(data.get('checkout'))
    payment = _as_dict(data.get('payment'))
    transparent = _as_dict(data.get('transparent'))
    subscription = _as_dict(data.get('subscription'))

    external_id = _first_text(
        checkout.get('externalId'),
        payment.get('externalId'),
        transparent.get('externalId'),
        subscription.get('externalId'),
    )

    if not external_id:
        return None

    period_started_at = _first_datetime(
        subscription.get('currentPeriodStart'),
        subscription.get('current_period_start'),
        payment.get('paidAt'),
        payment.get('paid_at'),
        checkout.get('paidAt'),
        checkout.get('paid_at'),
        data.get('paidAt'),
        data.get('createdAt'),
        payload.get('createdAt'),
    )
    explicit_period_end = _first_datetime(
        subscription.get('currentPeriodEnd'),
        subscription.get('current_period_end'),
        subscription.get('nextBillingDate'),
        subscription.get('next_billing_date'),
        subscription.get('expiresAt'),
        subscription.get('expires_at'),
        payment.get('nextBillingDate'),
        payment.get('next_billing_date'),
    )

    return WebhookContext(
        external_id=external_id,
        external_subscription_id=_first_text(
            subscription.get('id'),
            checkout.get('subscriptionId'),
            payment.get('subscriptionId'),
            transparent.get('subscriptionId'),
        ),
        checkout_id=_first_text(checkout.get('id'), payment.get('id')),
        checkout_url=_first_text(checkout.get('url')),
        current_period_ends_at=resolve_period_end(
            plan_id=parse_plan_id(external_id),
            explicit_period_end=explicit_period_end,
            period_started_at=period_started_at,
        ),
    )


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def _first_datetime(*values: object) -> datetime | None:
    for value in values:
        parsed = parse_api_datetime(value)
        if parsed is not None:
            return parsed

    return None

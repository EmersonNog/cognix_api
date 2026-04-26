from __future__ import annotations

from sqlalchemy.orm import Session

from ..coupons.redemptions import record_coupon_redeemed
from ..shared.external_ids import parse_coupon_context, parse_plan_id
from ..shared.plans import get_plan_config
from ..subscriptions.periods import parse_api_datetime, resolve_period_end
from ..subscriptions.records import (
    mark_subscription_active,
    mark_subscription_cancelled_by_external_id,
)


def handle_abacatepay_webhook(db: Session, payload: dict) -> dict[str, str]:
    event = payload.get('event')

    if event not in {
        'checkout.completed',
        'subscription.completed',
        'subscription.cancelled',
    }:
        return {'status': 'ignored'}

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
        return {'status': 'ignored'}

    external_subscription_id = _first_text(
        subscription.get('id'),
        checkout.get('subscriptionId'),
        payment.get('subscriptionId'),
        transparent.get('subscriptionId'),
    )
    checkout_id = _first_text(checkout.get('id'), payment.get('id'))
    checkout_url = _first_text(checkout.get('url'))
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
    current_period_ends_at = resolve_period_end(
        plan_id=parse_plan_id(external_id),
        explicit_period_end=explicit_period_end,
        period_started_at=period_started_at,
    )

    if event == 'subscription.cancelled':
        mark_subscription_cancelled_by_external_id(
            db,
            external_id=external_id,
            external_subscription_id=external_subscription_id,
        )
        db.commit()
        return {'status': 'ok'}

    mark_subscription_active(
        db,
        external_id=external_id,
        external_subscription_id=external_subscription_id,
        checkout_id=checkout_id,
        checkout_url=checkout_url,
        current_period_ends_at=current_period_ends_at,
    )

    coupon_context = parse_coupon_context(external_id)
    if not coupon_context:
        db.commit()
        return {'status': 'ok'}

    plan = get_plan_config(coupon_context['plan_id'])
    record_coupon_redeemed(
        db,
        coupon_code=coupon_context['coupon_code'],
        tax_id_hash=coupon_context['tax_id_hash'],
        email_hash=coupon_context['email_hash'],
        plan_id=coupon_context['plan_id'],
        product_id=plan.product_id,
        external_id=external_id,
        checkout_id=checkout_id,
        checkout_url=checkout_url,
    )
    db.commit()

    return {'status': 'ok'}


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def _first_datetime(*values: object):
    for value in values:
        parsed = parse_api_datetime(value)
        if parsed is not None:
            return parsed

    return None

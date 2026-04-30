from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.services.payments.abacatepay.checkout.attribution import attribution_from_json
from app.services.payments.abacatepay.shared.external_ids import (
    parse_coupon_context,
    parse_plan_id,
)
from app.services.payments.abacatepay.shared.plans import (
    get_plan_config,
    resolve_checkout_price_cents,
)
from app.services.payments.abacatepay.subscriptions.periods import parse_api_datetime


def build_utmify_paid_order_payload(
    subscription: dict,
    webhook_payload: dict,
) -> dict[str, Any]:
    external_id = str(subscription.get('external_id') or '')
    plan_id = str(subscription.get('plan_id') or parse_plan_id(external_id) or '')
    plan = get_plan_config(plan_id)
    coupon_applied = parse_coupon_context(external_id) is not None
    amount_cents = resolve_checkout_price_cents(
        plan,
        coupon_applied=coupon_applied,
    )
    attribution = attribution_from_json(subscription.get('attribution_json'))
    approved_at = _first_datetime_from_payload(webhook_payload)
    created_at = _first_datetime(
        _nested(webhook_payload, 'data', 'checkout', 'createdAt'),
        _nested(webhook_payload, 'data', 'payment', 'createdAt'),
        _nested(webhook_payload, 'data', 'subscription', 'createdAt'),
        webhook_payload.get('createdAt'),
    )
    product_id = str(subscription.get('product_id') or plan.product_id)

    return {
        'isTest': settings.utmify_is_test,
        'status': 'paid',
        'orderId': external_id,
        'platform': settings.utmify_platform,
        'paymentMethod': _payment_method(webhook_payload),
        'createdAt': _format_utmify_datetime(created_at or approved_at),
        'approvedDate': _format_utmify_datetime(approved_at),
        'refundedAt': None,
        'customer': _customer_payload(webhook_payload),
        'products': [
            {
                'id': product_id,
                'name': plan.name or product_id,
                'planId': plan_id,
                'planName': plan.name or plan_id,
                'quantity': 1,
                'priceInCents': amount_cents,
            }
        ],
        'trackingParameters': {
            'src': attribution.get('src') or attribution.get('xcod'),
            'sck': attribution.get('sck'),
            'utm_source': attribution.get('utm_source'),
            'utm_campaign': attribution.get('utm_campaign'),
            'utm_medium': attribution.get('utm_medium'),
            'utm_content': attribution.get('utm_content'),
            'utm_term': attribution.get('utm_term'),
        },
        'commission': {
            'totalPriceInCents': amount_cents,
            'gatewayFeeInCents': 0,
            'userCommissionInCents': amount_cents,
            'currency': 'BRL',
        },
    }


def _customer_payload(webhook_payload: dict) -> dict[str, str | None]:
    customer = _first_dict(
        _nested(webhook_payload, 'data', 'customer'),
        _nested(webhook_payload, 'data', 'checkout', 'customer'),
        _nested(webhook_payload, 'data', 'payment', 'customer'),
        _nested(webhook_payload, 'data', 'subscription', 'customer'),
        _nested(webhook_payload, 'data', 'transparent', 'customer'),
    )
    metadata = _first_dict(
        _nested(webhook_payload, 'data', 'metadata'),
        _nested(webhook_payload, 'data', 'checkout', 'metadata'),
        _nested(webhook_payload, 'data', 'payment', 'metadata'),
        _nested(webhook_payload, 'data', 'subscription', 'metadata'),
    )

    return {
        'name': _first_text(
            customer.get('name'),
            customer.get('fullName'),
            metadata.get('submittedName'),
            'Cliente Cognix',
        ),
        'email': _first_text(customer.get('email'), metadata.get('submittedEmail')),
        'phone': _digits_or_none(customer.get('phone')),
        'document': _unmasked_digits_or_none(
            customer.get('taxId'),
            customer.get('document'),
        ),
        'country': 'BR',
    }


def _payment_method(webhook_payload: dict) -> str:
    method = _first_text(
        _nested(webhook_payload, 'data', 'payment', 'method'),
        _nested(webhook_payload, 'data', 'payment', 'paymentMethod'),
        _nested(webhook_payload, 'data', 'checkout', 'method'),
    )
    normalized = (method or '').lower()

    if 'pix' in normalized:
        return 'pix'
    if 'boleto' in normalized or 'bank_slip' in normalized:
        return 'boleto'

    return 'credit_card'


def _first_datetime_from_payload(webhook_payload: dict) -> datetime:
    return _first_datetime(
        _nested(webhook_payload, 'data', 'payment', 'paidAt'),
        _nested(webhook_payload, 'data', 'payment', 'paid_at'),
        _nested(webhook_payload, 'data', 'checkout', 'paidAt'),
        _nested(webhook_payload, 'data', 'checkout', 'paid_at'),
        _nested(webhook_payload, 'data', 'paidAt'),
        webhook_payload.get('createdAt'),
    ) or utc_now()


def _format_utmify_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def _first_datetime(*values: object) -> datetime | None:
    for value in values:
        parsed = parse_api_datetime(value)
        if parsed is not None:
            return parsed

    return None


def _first_dict(*values: object) -> dict:
    for value in values:
        if isinstance(value, dict):
            return value

    return {}


def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def _nested(value: object, *keys: str) -> object:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def _digits_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    digits = ''.join(character for character in value if character.isdigit())
    return digits or None


def _unmasked_digits_or_none(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and '*' not in value:
            digits = _digits_or_none(value)
            if digits:
                return digits

    return None

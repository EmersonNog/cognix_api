from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .checkout import normalize_checkout_input, validate_checkout_input
from .client import create_customer, create_subscription
from .coupons import (
    ensure_coupon_not_redeemed,
    hash_identifier,
    record_coupon_redeemed,
    should_apply_coupon,
)
from .plans import get_plan_config


EXTERNAL_ID_SEPARATOR = '.'


def _new_external_id(
    plan_id: str,
    *,
    coupon_code: str | None = None,
    tax_id_hash: str | None = None,
    email_hash: str | None = None,
) -> str:
    created_at = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    nonce = secrets.token_hex(4)

    if coupon_code and tax_id_hash and email_hash:
        return EXTERNAL_ID_SEPARATOR.join(
            (
                'cognix',
                plan_id,
                created_at,
                coupon_code,
                tax_id_hash,
                email_hash,
                nonce,
            )
        )

    return EXTERNAL_ID_SEPARATOR.join(('cognix', plan_id, created_at, nonce))


def create_subscription_checkout(
    db: Session,
    *,
    plan_id: str,
    name: str,
    email: str,
    tax_id: str,
    coupon_code: str | None,
) -> str:
    checkout = normalize_checkout_input(
        plan_id=plan_id,
        name=name,
        email=email,
        tax_id=tax_id,
        coupon_code=coupon_code,
    )
    validate_checkout_input(checkout)

    plan = get_plan_config(checkout.plan_id)
    # Only confirmed payments block a CPF/email from using the coupon again.
    apply_coupon = should_apply_coupon(checkout, plan)
    allowed_coupon_code = checkout.coupon_code if apply_coupon else None
    tax_id_hash = hash_identifier(checkout.tax_id)
    email_hash = hash_identifier(checkout.email)
    external_id = _new_external_id(
        checkout.plan_id,
        coupon_code=checkout.coupon_code if apply_coupon else None,
        tax_id_hash=tax_id_hash if apply_coupon else None,
        email_hash=email_hash if apply_coupon else None,
    )

    if apply_coupon:
        ensure_coupon_not_redeemed(
            db,
            coupon_code=checkout.coupon_code,
            tax_id_hash=tax_id_hash,
            email_hash=email_hash,
        )

    try:
        customer_id = create_customer(checkout, tax_id_hash)
        checkout_url, _checkout_id = create_subscription(
            checkout=checkout,
            plan=plan,
            customer_id=customer_id,
            external_id=external_id,
            tax_id_hash=tax_id_hash,
            allowed_coupon_code=allowed_coupon_code,
        )

        db.commit()
        return checkout_url
    except Exception:
        db.rollback()
        raise


def handle_abacatepay_webhook(db: Session, payload: dict) -> dict[str, str]:
    event = payload.get('event')

    if event not in {'checkout.completed', 'subscription.completed'}:
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

    coupon_context = _parse_coupon_context(external_id)

    if not coupon_context:
        return {'status': 'ignored'}

    plan = get_plan_config(coupon_context['plan_id'])
    record_coupon_redeemed(
        db,
        coupon_code=coupon_context['coupon_code'],
        tax_id_hash=coupon_context['tax_id_hash'],
        email_hash=coupon_context['email_hash'],
        plan_id=coupon_context['plan_id'],
        product_id=plan.product_id,
        external_id=external_id,
        checkout_id=_first_text(checkout.get('id'), payment.get('id')),
        checkout_url=_first_text(checkout.get('url')),
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


def _parse_coupon_context(external_id: str) -> dict[str, str] | None:
    parts = external_id.split(EXTERNAL_ID_SEPARATOR)

    if len(parts) != 7 or parts[0] != 'cognix':
        return None

    _, plan_id, _created_at, coupon_code, tax_id_hash, email_hash, _nonce = parts

    if not coupon_code or not tax_id_hash or not email_hash:
        return None

    return {
        'plan_id': plan_id,
        'coupon_code': coupon_code,
        'tax_id_hash': tax_id_hash,
        'email_hash': email_hash,
    }

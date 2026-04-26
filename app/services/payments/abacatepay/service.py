from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .checkout import normalize_checkout_input, validate_checkout_input
from .client import create_customer, create_subscription
from .coupons import hash_identifier
from .plans import get_plan_config


def _new_external_id(plan_id: str) -> str:
    return (
        f'cognix-{plan_id}-'
        f'{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}-'
        f'{secrets.token_hex(4)}'
    )


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
    # Do not attach or reserve coupons while the checkout is still unpaid.
    apply_coupon = False
    external_id = _new_external_id(checkout.plan_id)
    tax_id_hash = hash_identifier(checkout.tax_id)

    try:
        customer_id = create_customer(checkout, tax_id_hash)
        checkout_url, _checkout_id = create_subscription(
            checkout=checkout,
            plan=plan,
            customer_id=customer_id,
            external_id=external_id,
            tax_id_hash=tax_id_hash,
            apply_coupon=apply_coupon,
        )

        db.commit()
        return checkout_url
    except Exception:
        db.rollback()
        raise

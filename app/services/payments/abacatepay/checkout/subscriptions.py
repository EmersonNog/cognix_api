from __future__ import annotations

from sqlalchemy.orm import Session

from .inputs import normalize_checkout_input, validate_checkout_input
from ..coupons.redemptions import ensure_coupon_not_redeemed
from .preparation import prepare_checkout_subscription
from ..gateway.customers import create_customer
from ..gateway.subscriptions import create_subscription
from ..subscriptions.persistence.records import record_subscription_checkout_created


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

    prepared = prepare_checkout_subscription(checkout)

    if prepared.apply_coupon:
        ensure_coupon_not_redeemed(
            db,
            coupon_code=checkout.coupon_code,
            tax_id_hash=prepared.tax_id_hash,
            email_hash=prepared.email_hash,
        )

    try:
        customer_id = create_customer(checkout, prepared.tax_id_hash)
        checkout_url, checkout_id = create_subscription(
            checkout=checkout,
            plan=prepared.plan,
            customer_id=customer_id,
            external_id=prepared.external_id,
            tax_id_hash=prepared.tax_id_hash,
            allowed_coupon_code=prepared.allowed_coupon_code,
        )
        record_subscription_checkout_created(
            db,
            plan_id=checkout.plan_id,
            product_id=prepared.plan.product_id,
            tax_id_hash=prepared.tax_id_hash,
            email_hash=prepared.email_hash,
            external_customer_id=customer_id,
            external_id=prepared.external_id,
            checkout_id=str(checkout_id) if checkout_id else None,
            checkout_url=checkout_url,
        )

        db.commit()
        return checkout_url
    except Exception:
        db.rollback()
        raise

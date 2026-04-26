from __future__ import annotations

from sqlalchemy.orm import Session

from .inputs import normalize_checkout_input, validate_checkout_input
from ..coupons.identifiers import hash_identifier
from ..coupons.redemptions import ensure_coupon_not_redeemed
from ..coupons.rules import should_apply_coupon
from ..gateway.customers import create_customer
from ..gateway.subscriptions import create_subscription
from ..shared.external_ids import new_external_id
from ..shared.plans import get_plan_config
from ..subscriptions.records import record_subscription_checkout_created

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
    apply_coupon = should_apply_coupon(checkout, plan)
    allowed_coupon_code = checkout.coupon_code if apply_coupon else None
    tax_id_hash = hash_identifier(checkout.tax_id)
    email_hash = hash_identifier(checkout.email)
    external_id = new_external_id(
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
        checkout_url, checkout_id = create_subscription(
            checkout=checkout,
            plan=plan,
            customer_id=customer_id,
            external_id=external_id,
            tax_id_hash=tax_id_hash,
            allowed_coupon_code=allowed_coupon_code,
        )
        record_subscription_checkout_created(
            db,
            plan_id=checkout.plan_id,
            product_id=plan.product_id,
            tax_id_hash=tax_id_hash,
            email_hash=email_hash,
            external_customer_id=customer_id,
            external_id=external_id,
            checkout_id=str(checkout_id) if checkout_id else None,
            checkout_url=checkout_url,
        )

        db.commit()
        return checkout_url
    except Exception:
        db.rollback()
        raise

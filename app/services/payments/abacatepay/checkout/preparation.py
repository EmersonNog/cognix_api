from __future__ import annotations

from dataclasses import dataclass

from .inputs import CheckoutInput
from ..coupons.identifiers import hash_identifier
from ..coupons.rules import should_apply_coupon
from ..shared.external_ids import new_external_id
from ..shared.plans import PlanConfig, get_plan_config

@dataclass(frozen=True)
class CheckoutPreparation:
    plan: PlanConfig
    apply_coupon: bool
    allowed_coupon_code: str | None
    tax_id_hash: str
    email_hash: str
    external_id: str

def prepare_checkout_subscription(checkout: CheckoutInput) -> CheckoutPreparation:
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

    return CheckoutPreparation(
        plan=plan,
        apply_coupon=apply_coupon,
        allowed_coupon_code=allowed_coupon_code,
        tax_id_hash=tax_id_hash,
        email_hash=email_hash,
        external_id=external_id,
    )

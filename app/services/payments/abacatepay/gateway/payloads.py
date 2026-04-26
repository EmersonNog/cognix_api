from __future__ import annotations

from typing import Any

from app.core.config import settings

from ..checkout.inputs import CheckoutInput
from ..shared.plans import PlanConfig

CHECKOUT_SOURCE = 'cognix_api'

def customer_payload(checkout: CheckoutInput, tax_id_hash: str) -> dict[str, Any]:
    return {
        'email': checkout.email,
        'name': checkout.name,
        'taxId': checkout.tax_id,
        'metadata': checkout_metadata(checkout, tax_id_hash),
    }


def subscription_payload(
    *,
    checkout: CheckoutInput,
    plan: PlanConfig,
    customer_id: str,
    external_id: str,
    tax_id_hash: str,
    allowed_coupon_code: str | None,
) -> dict[str, Any]:
    site_url = settings.abacatepay_app_url.rstrip('/')
    payload: dict[str, Any] = {
        'items': [{'id': plan.product_id, 'quantity': 1}],
        'customerId': customer_id,
        'methods': ['CARD'],
        'externalId': external_id,
        'returnUrl': f'{site_url}/assinatura?plano={checkout.plan_id}',
        'completionUrl': f'{site_url}/assinatura?status=sucesso&plano={checkout.plan_id}',
        'metadata': checkout_metadata(checkout, tax_id_hash),
    }

    if allowed_coupon_code:
        payload['coupons'] = [allowed_coupon_code]
        payload['metadata']['firstMonthDiscountCoupon'] = allowed_coupon_code

    return payload


def checkout_metadata(checkout: CheckoutInput, tax_id_hash: str) -> dict[str, str]:
    return {
        'source': CHECKOUT_SOURCE,
        'planId': checkout.plan_id,
        'submittedName': checkout.name,
        'submittedEmail': checkout.email,
        'submittedTaxIdHash': tax_id_hash,
        'submittedCouponCode': checkout.coupon_code,
    }

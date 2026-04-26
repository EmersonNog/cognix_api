from __future__ import annotations

from fastapi import HTTPException

from ..checkout.inputs import CheckoutInput
from ..shared.plans import PlanConfig
from .http import post_abacatepay
from .payloads import subscription_payload

def create_subscription(
    *,
    checkout: CheckoutInput,
    plan: PlanConfig,
    customer_id: str,
    external_id: str,
    tax_id_hash: str,
    allowed_coupon_code: str | None,
) -> tuple[str, object]:
    subscription_response = post_abacatepay(
        '/subscriptions/create',
        subscription_payload(
            checkout=checkout,
            plan=plan,
            customer_id=customer_id,
            external_id=external_id,
            tax_id_hash=tax_id_hash,
            allowed_coupon_code=allowed_coupon_code,
        ),
    )
    checkout_data = subscription_response.get('data', {})
    checkout_url = checkout_data.get('url')
    checkout_id = checkout_data.get('id')

    if not isinstance(checkout_url, str) or not checkout_url.startswith('http'):
        raise HTTPException(
            status_code=502,
            detail='A AbacatePay não retornou a URL do checkout.',
        )

    return checkout_url, checkout_id

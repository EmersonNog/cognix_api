from __future__ import annotations

from fastapi import HTTPException

from ..checkout.inputs import CheckoutInput
from .http import post_abacatepay
from .payloads import customer_payload


def create_customer(checkout: CheckoutInput, tax_id_hash: str) -> str:
    customer_response = post_abacatepay(
        '/customers/create',
        customer_payload(checkout, tax_id_hash),
    )
    customer_id = customer_response.get('data', {}).get('id')

    if not isinstance(customer_id, str) or not customer_id:
        raise HTTPException(
            status_code=502,
            detail='A AbacatePay não retornou o cliente do checkout.',
        )

    return customer_id

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.core.config import settings

from .checkout import CheckoutInput
from .plans import PlanConfig

ABACATEPAY_TIMEOUT_SECONDS = 25
CHECKOUT_SOURCE = 'cognix_api'


def create_customer(checkout: CheckoutInput, tax_id_hash: str) -> str:
    customer_response = _post('/customers/create', _customer_payload(checkout, tax_id_hash))
    customer_id = customer_response.get('data', {}).get('id')

    if not isinstance(customer_id, str) or not customer_id:
        raise HTTPException(
            status_code=502,
            detail='A AbacatePay não retornou o cliente do checkout.',
        )

    return customer_id


def create_subscription(
    *,
    checkout: CheckoutInput,
    plan: PlanConfig,
    customer_id: str,
    external_id: str,
    tax_id_hash: str,
    apply_coupon: bool,
) -> tuple[str, object]:
    subscription_response = _post(
        '/subscriptions/create',
        _subscription_payload(
            checkout=checkout,
            plan=plan,
            customer_id=customer_id,
            external_id=external_id,
            tax_id_hash=tax_id_hash,
            apply_coupon=apply_coupon,
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


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    api_key = settings.abacatepay_api_key

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail='Configure ABACATEPAY_API_KEY no servidor.',
        )

    request = Request(
        f'{settings.abacatepay_api_base_url.rstrip("/")}{path}',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=ABACATEPAY_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

        message = payload.get('error') or payload.get('message') or 'A AbacatePay recusou a requisição.'
        raise HTTPException(status_code=502, detail=str(message)) from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail='Falha ao conectar na AbacatePay.') from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=502,
            detail='A AbacatePay retornou uma resposta inesperada.',
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail='A AbacatePay retornou uma resposta inesperada.',
        )

    if payload.get('success') is False:
        raise HTTPException(
            status_code=502,
            detail=str(payload.get('error') or 'A AbacatePay recusou a requisição.'),
        )

    return payload


def _customer_payload(checkout: CheckoutInput, tax_id_hash: str) -> dict[str, Any]:
    return {
        'email': checkout.email,
        'name': checkout.name,
        'taxId': checkout.tax_id,
        'metadata': _checkout_metadata(checkout, tax_id_hash),
    }


def _subscription_payload(
    *,
    checkout: CheckoutInput,
    plan: PlanConfig,
    customer_id: str,
    external_id: str,
    tax_id_hash: str,
    apply_coupon: bool,
) -> dict[str, Any]:
    site_url = settings.abacatepay_app_url.rstrip('/')
    payload: dict[str, Any] = {
        'items': [{'id': plan.product_id, 'quantity': 1}],
        'customerId': customer_id,
        'methods': ['CARD'],
        'externalId': external_id,
        'returnUrl': f'{site_url}/assinatura?plano={checkout.plan_id}',
        'completionUrl': f'{site_url}/assinatura?status=sucesso&plano={checkout.plan_id}',
        'metadata': _checkout_metadata(checkout, tax_id_hash),
    }

    if apply_coupon:
        payload['coupons'] = [checkout.coupon_code]
        payload['metadata']['firstMonthDiscountCoupon'] = checkout.coupon_code

    return payload


def _checkout_metadata(checkout: CheckoutInput, tax_id_hash: str) -> dict[str, str]:
    return {
        'source': CHECKOUT_SOURCE,
        'planId': checkout.plan_id,
        'submittedName': checkout.name,
        'submittedEmail': checkout.email,
        'submittedTaxIdHash': tax_id_hash,
        'submittedCouponCode': checkout.coupon_code,
    }

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings

from .checkout import CheckoutInput
from .plans import PlanConfig

ABACATEPAY_TIMEOUT_SECONDS = 25
CHECKOUT_SOURCE = 'cognix_api'
ABACATEPAY_USER_AGENT = 'CognixHub/1.0 (+https://mkt.cognix-hub.com)'


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

    try:
        with httpx.Client(
            base_url=settings.abacatepay_api_base_url.rstrip('/'),
            headers={
                'Accept': 'application/json',
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'User-Agent': ABACATEPAY_USER_AGENT,
            },
            timeout=httpx.Timeout(ABACATEPAY_TIMEOUT_SECONDS),
            follow_redirects=False,
        ) as client:
            response = client.post(path, json=body)
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=502,
            detail='Tempo esgotado ao conectar na AbacatePay.',
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail='Falha ao conectar na AbacatePay.',
        ) from exc

    payload = _parse_response_payload(response)

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=_error_message(payload, response.text),
        )

    if payload.get('success') is False:
        raise HTTPException(
            status_code=502,
            detail=_error_message(payload, response.text),
        )

    return payload


def _parse_response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail='A AbacatePay retornou uma resposta inesperada.',
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail='A AbacatePay retornou uma resposta inesperada.',
        )

    return payload


def _error_message(payload: dict[str, Any], raw_error: str) -> str:
    for field in ('error', 'message', 'detail'):
        value = payload.get(field)

        if isinstance(value, str) and value.strip():
            return value

        if isinstance(value, dict):
            nested_message = _error_message(value, '')

            if nested_message != 'A AbacatePay recusou a requisição.':
                return nested_message

    errors = payload.get('errors')

    if isinstance(errors, list) and errors:
        first_error = errors[0]

        if isinstance(first_error, str) and first_error.strip():
            return first_error

        if isinstance(first_error, dict):
            return _error_message(first_error, '')

    if raw_error.strip():
        return raw_error.strip()[:600]

    return 'A AbacatePay recusou a requisição.'


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

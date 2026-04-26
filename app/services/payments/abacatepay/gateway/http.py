from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings


ABACATEPAY_TIMEOUT_SECONDS = 25
ABACATEPAY_USER_AGENT = 'CognixHub/1.0 (+https://mkt.cognix-hub.com)'


def post_abacatepay(path: str, body: dict[str, Any]) -> dict[str, Any]:
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
            detail='A AbacatePay não retornou uma resposta inesperada.',
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail='A AbacatePay não retornou uma resposta inesperada.',
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

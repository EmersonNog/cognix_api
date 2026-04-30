from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings

UTMIFY_TIMEOUT_SECONDS = 15


def post_utmify_order(payload: dict[str, Any]) -> None:
    token = settings.utmify_api_token
    if not token:
        return

    try:
        with httpx.Client(
            timeout=httpx.Timeout(UTMIFY_TIMEOUT_SECONDS),
            follow_redirects=False,
        ) as client:
            response = client.post(
                settings.utmify_orders_url,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'x-api-token': token,
                },
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise RuntimeError('Tempo esgotado ao conectar na UTMify.') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError('Falha ao conectar na UTMify.') from exc

    if response.is_error:
        raise RuntimeError(_utmify_error_message(response))


def _utmify_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        for field in ('message', 'error', 'detail'):
            value = payload.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()[:600]

    return response.text.strip()[:600] or 'A UTMify recusou a venda.'

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import google.auth
from google.auth.exceptions import DefaultCredentialsError, RefreshError
import httpx
from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from app.core.config import settings


ANDROID_PUBLISHER_SCOPE = 'https://www.googleapis.com/auth/androidpublisher'
ANDROID_PUBLISHER_BASE_URL = (
    'https://androidpublisher.googleapis.com/androidpublisher/v3'
)
GOOGLE_PLAY_TIMEOUT_SECONDS = 15
_NO_JSON_BODY = object()


def fetch_google_play_subscription_purchase(
    *,
    package_name: str,
    purchase_token: str,
) -> dict[str, Any]:
    response = _request_google_play(
        'GET',
        _subscription_purchase_url(
            package_name=package_name,
            purchase_token=purchase_token,
        ),
        timeout_detail='Tempo esgotado ao consultar o Google Play.',
        connection_detail='Falha ao conectar no Google Play.',
    )
    payload = _parse_response_payload(response)
    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=_google_play_error_message(payload, response.text),
        )

    return payload


def acknowledge_google_play_subscription_purchase(
    *,
    package_name: str,
    product_id: str,
    purchase_token: str,
) -> None:
    response = _request_google_play(
        'POST',
        _subscription_acknowledgement_url(
            package_name=package_name,
            product_id=product_id,
            purchase_token=purchase_token,
        ),
        timeout_detail='Tempo esgotado ao reconhecer a compra no Google Play.',
        connection_detail='Falha ao reconhecer a compra no Google Play.',
        json_body={},
    )

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=_google_play_error_message(
                _parse_optional_response_payload(response),
                response.text,
            ),
        )


def _subscription_purchase_url(
    *,
    package_name: str,
    purchase_token: str,
) -> str:
    safe_package_name = quote(package_name, safe='')
    safe_purchase_token = quote(purchase_token, safe='')
    return (
        f'{ANDROID_PUBLISHER_BASE_URL}/applications/{safe_package_name}'
        f'/purchases/subscriptionsv2/tokens/{safe_purchase_token}'
    )


def _subscription_acknowledgement_url(
    *,
    package_name: str,
    product_id: str,
    purchase_token: str,
) -> str:
    safe_package_name = quote(package_name, safe='')
    safe_product_id = quote(product_id, safe='')
    safe_purchase_token = quote(purchase_token, safe='')
    return (
        f'{ANDROID_PUBLISHER_BASE_URL}/applications/{safe_package_name}'
        f'/purchases/subscriptions/{safe_product_id}'
        f'/tokens/{safe_purchase_token}:acknowledge'
    )


def _request_google_play(
    method: str,
    url: str,
    *,
    timeout_detail: str,
    connection_detail: str,
    json_body: object = _NO_JSON_BODY,
) -> httpx.Response:
    kwargs: dict[str, Any] = {
        'headers': _google_play_headers(
            include_content_type=json_body is not _NO_JSON_BODY
        ),
        'timeout': httpx.Timeout(GOOGLE_PLAY_TIMEOUT_SECONDS),
    }
    if json_body is not _NO_JSON_BODY:
        kwargs['json'] = json_body

    try:
        return httpx.request(method, url, **kwargs)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=502, detail=timeout_detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=connection_detail) from exc


def _google_play_headers(*, include_content_type: bool = False) -> dict[str, str]:
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {_google_play_access_token()}',
    }
    if include_content_type:
        headers['Content-Type'] = 'application/json'

    return headers


def _google_play_access_token() -> str:
    credentials_path = settings.google_play_service_account_credentials
    scopes = [ANDROID_PUBLISHER_SCOPE]

    try:
        if credentials_path:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=scopes,
            )
        else:
            credentials, _ = google.auth.default(scopes=scopes)

        credentials.refresh(Request())
    except (DefaultCredentialsError, FileNotFoundError, RefreshError) as exc:
        raise HTTPException(
            status_code=500,
            detail='Configure as credenciais da Google Play Developer API.',
        ) from exc
    token = credentials.token
    if not token:
        raise HTTPException(
            status_code=500,
            detail='Não foi possível autenticar na Google Play Developer API.',
        )

    return token


def _parse_response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail='O Google Play retornou uma resposta inesperada.',
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail='O Google Play retornou uma resposta inesperada.',
        )

    return payload


def _parse_optional_response_payload(response: httpx.Response) -> dict[str, Any]:
    if not response.text.strip():
        return {}

    try:
        payload = response.json()
    except ValueError:
        return {}

    return payload if isinstance(payload, dict) else {}


def _google_play_error_message(payload: dict[str, Any], raw_error: str) -> str:
    error = payload.get('error')
    if isinstance(error, dict):
        message = error.get('message')
        if isinstance(message, str) and message.strip():
            return message.strip()

    if raw_error.strip():
        return raw_error.strip()[:600]

    return 'O Google Play recusou a validação da assinatura.'

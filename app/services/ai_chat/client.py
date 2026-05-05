from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings

_GEMINI_GENERATE_CONTENT_URL = (
    'https://generativelanguage.googleapis.com/v1beta/models/'
    '{model}:generateContent'
)

def gemini_available() -> bool:
    return bool(settings.gemini_api_key and settings.gemini_api_key.strip())

def generate_with_gemini(prompt: str) -> str:
    envelope = _request_gemini_chat_completion(prompt)
    return _extract_gemini_content(envelope)

def _request_gemini_chat_completion(prompt: str) -> dict[str, Any]:
    endpoint = _GEMINI_GENERATE_CONTENT_URL.format(model=settings.gemini_model)
    request_payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': float(settings.ai_chat_temperature),
            'maxOutputTokens': int(settings.ai_chat_max_output_tokens),
        },
    }

    try:
        with httpx.Client(timeout=float(settings.ai_chat_timeout_seconds)) as client:
            response = client.post(
                endpoint,
                headers={
                    'x-goog-api-key': settings.gemini_api_key,
                    'Content-Type': 'application/json',
                },
                json=request_payload,
            )
            response.raise_for_status()
            envelope = response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f'Gemini error: {exc.response.status_code} {_read_error(exc)}'.strip(),
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f'Gemini unavailable: {exc}') from exc

    if not isinstance(envelope, dict):
        raise HTTPException(status_code=502, detail='Invalid Gemini response')
    return envelope

def _extract_gemini_content(envelope: dict[str, Any]) -> str:
    candidates = envelope.get('candidates')
    if not isinstance(candidates, list):
        raise HTTPException(status_code=502, detail='Empty Gemini response')

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get('content')
        if not isinstance(content, dict):
            continue
        parts = content.get('parts')
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = str(part.get('text') or '').strip()
            if text:
                return text

    raise HTTPException(status_code=502, detail='Empty Gemini response')

def _read_error(exc: httpx.HTTPStatusError) -> str:
    try:
        return exc.response.text
    except Exception:
        return ''

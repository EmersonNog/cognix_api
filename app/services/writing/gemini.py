import json
import urllib.error
import urllib.request

from fastapi import HTTPException

from app.core.config import settings

from .schemas import build_writing_feedback_schema


def gemini_available() -> bool:
    return bool(settings.gemini_api_key and settings.gemini_api_key.strip())


def generate_with_gemini(prompt: str) -> dict:
    request = _build_request(prompt)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f'Gemini error: {exc.code} {_read_error_body(exc)}'.strip(),
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f'Gemini unavailable: {exc}') from exc

    return _extract_json_payload(raw)


def _build_request(prompt: str) -> urllib.request.Request:
    endpoint = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{settings.gemini_model}:generateContent'
    )
    request_payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'responseMimeType': 'application/json',
            'responseJsonSchema': build_writing_feedback_schema(),
            'temperature': 0.25,
        },
    }
    return urllib.request.Request(
        endpoint,
        data=json.dumps(request_payload).encode('utf-8'),
        headers={
            'x-goog-api-key': settings.gemini_api_key,
            'Content-Type': 'application/json',
        },
        method='POST',
    )


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode('utf-8')
    except Exception:
        return ''


def _extract_json_payload(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail='Invalid Gemini envelope') from exc

    for candidate in data.get('candidates') or []:
        content = candidate.get('content') or {}
        for part in content.get('parts') or []:
            text = part.get('text')
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=502, detail='Invalid Gemini JSON') from exc

    raise HTTPException(status_code=502, detail='Empty Gemini response')

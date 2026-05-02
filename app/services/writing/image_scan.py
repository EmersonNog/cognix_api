import base64
import binascii
import json
import urllib.error
import urllib.request

from fastapi import HTTPException

from app.core.config import settings

from .prompt import build_writing_image_scan_prompt
from .schemas import build_writing_image_scan_schema

_ALLOWED_IMAGE_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
_MAX_IMAGE_BYTES = 8 * 1024 * 1024


def scan_writing_image(payload: dict, *, user_id: int) -> dict:
    _ensure_gemini_available()
    image_bytes, mime_type = _decode_image_payload(payload)
    response_payload = _generate_image_scan_with_gemini(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=build_writing_image_scan_prompt(user_id),
    )
    return _normalize_image_scan_response(response_payload)


def _ensure_gemini_available() -> None:
    if not settings.gemini_api_key or not settings.gemini_api_key.strip():
        raise HTTPException(status_code=503, detail='Gemini API key is not configured')


def _decode_image_payload(payload: dict) -> tuple[bytes, str]:
    raw_image = payload.get('image_base64')
    if not isinstance(raw_image, str) or not raw_image.strip():
        raise HTTPException(status_code=422, detail='image_base64 is required')

    mime_type = _normalize_mime_type(payload.get('mime_type'))
    try:
        image_bytes = base64.b64decode(raw_image, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail='image_base64 is invalid') from exc

    if not image_bytes:
        raise HTTPException(status_code=422, detail='Image is empty')
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail='Image must be up to 8MB')

    return image_bytes, mime_type


def _normalize_mime_type(value: object) -> str:
    mime_type = value.strip().lower() if isinstance(value, str) else ''
    if mime_type == 'image/jpg':
        mime_type = 'image/jpeg'

    if mime_type not in _ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail='Image must be JPEG, PNG or WEBP',
        )
    return mime_type


def _generate_image_scan_with_gemini(
    *,
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
) -> dict:
    request = _build_request(image_bytes=image_bytes, mime_type=mime_type, prompt=prompt)

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f'Gemini error: {exc.code} {_read_error_body(exc)}'.strip(),
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f'Gemini unavailable: {exc}') from exc

    return _extract_json_payload(raw)


def _build_request(
    *,
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
) -> urllib.request.Request:
    endpoint = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{settings.gemini_image_model}:generateContent'
    )
    request_payload = {
        'contents': [
            {
                'parts': [
                    {
                        'inline_data': {
                            'mime_type': mime_type,
                            'data': base64.b64encode(image_bytes).decode('ascii'),
                        },
                    },
                    {'text': prompt},
                ],
            },
        ],
        'generationConfig': {
            'responseMimeType': 'application/json',
            'responseJsonSchema': build_writing_image_scan_schema(),
            'temperature': 0.05,
            'mediaResolution': 'MEDIA_RESOLUTION_HIGH',
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


def _normalize_image_scan_response(payload: dict) -> dict:
    text = _string(payload.get('text'))
    warnings = [_string(item) for item in _list(payload.get('warnings'))]
    warnings = [item for item in warnings if item][:5]
    confidence = _clamp_float(payload.get('confidence'), 0.0, 1.0)

    return {
        'text': text,
        'confidence': confidence,
        'warnings': warnings,
    }


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ''


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _clamp_float(value: object, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))

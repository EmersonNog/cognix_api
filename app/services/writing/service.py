import json
import urllib.error
import urllib.request

from fastapi import HTTPException

from app.core.config import settings
from .normalize import normalize_writing_feedback
from .prompt import build_writing_prompt
from .schemas import build_writing_feedback_schema


def gemini_available() -> bool:
    return bool(settings.gemini_api_key and settings.gemini_api_key.strip())


def analyze_writing(payload: dict, user_id: int) -> dict:
    if not gemini_available():
        raise HTTPException(status_code=503, detail='Gemini API key is not configured')

    _validate_payload(payload)
    response_payload = _generate_with_gemini(build_writing_prompt(payload, user_id))
    return normalize_writing_feedback(response_payload)


def _validate_payload(payload: dict) -> None:
    final_text = payload.get('final_text')
    if not isinstance(final_text, str) or len(final_text.strip()) < 80:
        raise HTTPException(
            status_code=422,
            detail='Texto final precisa ter pelo menos 80 caracteres.',
        )


def _generate_with_gemini(prompt: str) -> dict:
    request_payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'responseMimeType': 'application/json',
            'responseJsonSchema': build_writing_feedback_schema(),
            'temperature': 0.25,
        },
    }
    endpoint = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{settings.gemini_model}:generateContent'
    )
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(request_payload).encode('utf-8'),
        headers={
            'x-goog-api-key': settings.gemini_api_key,
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode('utf-8')
        except Exception:
            body = ''
        raise HTTPException(
            status_code=502,
            detail=f'Gemini error: {exc.code} {body}'.strip(),
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f'Gemini unavailable: {exc}') from exc

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

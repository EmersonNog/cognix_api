import json
import urllib.request

from app.core.config import settings


def gemini_available() -> bool:
    return bool(settings.gemini_api_key and settings.gemini_api_key.strip())


def generate_insight(prompt: str) -> dict | None:
    endpoint = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{settings.gemini_model}:generateContent'
    )
    request_payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'responseMimeType': 'application/json',
            'responseJsonSchema': _build_response_schema(),
            'temperature': 0.35,
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(request_payload).encode('utf-8'),
        headers={
            'x-goog-api-key': settings.gemini_api_key,
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode('utf-8')

    envelope = json.loads(raw)
    for candidate in envelope.get('candidates') or []:
        content = candidate.get('content') or {}
        for part in content.get('parts') or []:
            text = part.get('text')
            if not text:
                continue
            payload = json.loads(text)
            title = str(payload.get('title') or '').strip()
            summary = str(payload.get('summary') or '').strip()
            priority = str(payload.get('priority') or '').strip()
            risk_level = str(payload.get('risk_level') or '').strip().lower()
            next_action = str(payload.get('next_action') or '').strip()
            try:
                confidence = float(payload.get('confidence'))
            except (TypeError, ValueError):
                confidence = 0.0

            if (
                title and
                summary and
                priority and
                risk_level and
                next_action
            ):
                return {
                    'title': title,
                    'summary': summary,
                    'priority': priority,
                    'risk_level': risk_level,
                    'next_action': next_action,
                    'confidence': max(0.0, min(confidence, 1.0)),
                }

    return None


def _build_response_schema() -> dict:
    return {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'summary': {'type': 'string'},
            'priority': {'type': 'string'},
            'risk_level': {'type': 'string'},
            'next_action': {'type': 'string'},
            'confidence': {'type': 'number'},
        },
        'required': [
            'title',
            'summary',
            'priority',
            'risk_level',
            'next_action',
            'confidence',
        ],
    }

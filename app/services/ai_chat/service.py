from typing import Any

from fastapi import HTTPException

from app.core.config import settings
from app.core.datetime_utils import to_api_iso, utc_now

from .client import gemini_available as _gemini_available
from .client import generate_with_gemini
from .prompt import build_gemini_chat_prompt
from .validation import normalize_chat_messages

def gemini_available() -> bool:
    return _gemini_available()

def generate_ai_chat_reply(payload: dict[str, Any], *, user_id: int) -> dict[str, Any]:
    _ensure_gemini_available()

    messages = normalize_chat_messages(payload.get('messages'))
    prompt = build_gemini_chat_prompt(messages, user_id=user_id)
    content = _generate_with_gemini(prompt)

    return {
        'message': {
            'role': 'assistant',
            'content': content,
            'created_at': to_api_iso(utc_now()),
        },
        'model': settings.gemini_model,
    }

def _ensure_gemini_available() -> None:
    if not gemini_available():
        raise HTTPException(status_code=503, detail='Gemini API key not configured')

def _generate_with_gemini(prompt: str) -> str:
    return generate_with_gemini(prompt)

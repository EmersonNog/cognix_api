from typing import Any

from fastapi import HTTPException

from app.core.config import settings

_ALLOWED_ROLES = {'user', 'assistant'}

def normalize_chat_messages(raw_messages: Any) -> list[dict[str, str]]:
    if not isinstance(raw_messages, list):
        raise HTTPException(status_code=422, detail='messages must be a list')

    normalized = _normalize_message_items(raw_messages)
    if not normalized:
        raise HTTPException(status_code=422, detail='message content is required')
    if normalized[-1]['role'] != 'user':
        raise HTTPException(status_code=422, detail='last message must be from user')

    max_messages = max(1, int(settings.ai_chat_max_messages))
    return normalized[-max_messages:]

def _normalize_message_items(raw_messages: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    max_content_chars = max(1, int(settings.ai_chat_max_content_chars))

    for raw_message in raw_messages:
        if not isinstance(raw_message, dict):
            raise HTTPException(status_code=422, detail='invalid chat message')

        role = str(raw_message.get('role') or '').strip().lower()
        content = str(raw_message.get('content') or '').strip()
        if not content:
            continue
        if role not in _ALLOWED_ROLES:
            raise HTTPException(status_code=422, detail='invalid chat role')

        normalized.append(
            {
                'role': role,
                'content': content[:max_content_chars],
            }
        )

    return normalized

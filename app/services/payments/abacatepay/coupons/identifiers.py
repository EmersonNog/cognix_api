from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException

from app.core.config import settings

def hash_identifier(value: str) -> str:
    secret = settings.abacatepay_hash_secret or settings.abacatepay_api_key

    if not secret:
        raise HTTPException(
            status_code=500,
            detail='Configure ABACATEPAY_HASH_SECRET no servidor.',
        )

    return hmac.new(
        secret.encode('utf-8'),
        value.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

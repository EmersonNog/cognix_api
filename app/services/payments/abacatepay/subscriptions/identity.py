from __future__ import annotations

from ..coupons.identifiers import hash_identifier

def hash_email(email: str | None) -> str | None:
    normalized_email = str(email or '').strip().lower()
    return hash_identifier(normalized_email) if normalized_email else None

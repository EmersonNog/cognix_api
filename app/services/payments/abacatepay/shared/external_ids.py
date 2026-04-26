from __future__ import annotations

import secrets
from datetime import datetime, timezone


EXTERNAL_ID_SEPARATOR = '.'


def new_external_id(
    plan_id: str,
    *,
    coupon_code: str | None = None,
    tax_id_hash: str | None = None,
    email_hash: str | None = None,
) -> str:
    created_at = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    nonce = secrets.token_hex(4)

    if coupon_code and tax_id_hash and email_hash:
        return EXTERNAL_ID_SEPARATOR.join(
            (
                'cognix',
                plan_id,
                created_at,
                coupon_code,
                tax_id_hash,
                email_hash,
                nonce,
            )
        )

    return EXTERNAL_ID_SEPARATOR.join(('cognix', plan_id, created_at, nonce))


def parse_coupon_context(external_id: str) -> dict[str, str] | None:
    parts = external_id.split(EXTERNAL_ID_SEPARATOR)

    if len(parts) != 7 or parts[0] != 'cognix':
        return None

    _, plan_id, _created_at, coupon_code, tax_id_hash, email_hash, _nonce = parts

    if not coupon_code or not tax_id_hash or not email_hash:
        return None

    return {
        'plan_id': plan_id,
        'coupon_code': coupon_code,
        'tax_id_hash': tax_id_hash,
        'email_hash': email_hash,
    }

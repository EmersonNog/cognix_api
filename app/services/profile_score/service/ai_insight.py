import json
from datetime import datetime
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import to_api_iso, utc_now
from app.db.models import get_users_table
from .ai_insight_client import gemini_available, generate_insight
from .ai_insight_prompt import build_insight_fingerprint, build_insight_prompt


def build_profile_ai_insight(
    db: Session,
    user_id: int,
    metrics: dict,
    score_data: dict,
) -> dict | None:
    fingerprint = build_insight_fingerprint(metrics, score_data)
    cached = _load_cached_insight(db, user_id=user_id)

    if cached and cached['fingerprint'] == fingerprint and not cached['expired']:
        return _serialize_insight_result(
            cached['insight'],
            generated_at=cached['generated_at'],
            cache_hit=True,
        )

    if not gemini_available():
        if not cached:
            return None
        return _serialize_insight_result(
            cached['insight'],
            generated_at=cached['generated_at'],
            cache_hit=True,
        )

    prompt = build_insight_prompt(metrics, score_data)
    try:
        insight = generate_insight(prompt)
    except Exception:
        if not cached:
            return None
        return _serialize_insight_result(
            cached['insight'],
            generated_at=cached['generated_at'],
            cache_hit=True,
        )

    if insight is None:
        if not cached:
            return None
        return _serialize_insight_result(
            cached['insight'],
            generated_at=cached['generated_at'],
            cache_hit=True,
        )

    generated_at = _store_cached_insight(
        db,
        user_id=user_id,
        fingerprint=fingerprint,
        insight=insight,
    )
    return _serialize_insight_result(insight, generated_at=generated_at, cache_hit=False)


def _load_cached_insight(db: Session, *, user_id: int) -> dict | None:
    users = get_users_table(settings.users_table)
    row = db.execute(
        select(
            users.c.profile_ai_insight_json,
            users.c.profile_ai_insight_fingerprint,
            users.c.profile_ai_insight_generated_at,
        ).where(users.c.id == user_id)
    ).mappings().first()
    if not row:
        return None

    raw_json = row.get('profile_ai_insight_json')
    fingerprint = str(row.get('profile_ai_insight_fingerprint') or '').strip()
    generated_at = _parse_stored_timestamp(row.get('profile_ai_insight_generated_at'))
    if not raw_json or not fingerprint:
        return None

    try:
        insight = json.loads(raw_json)
    except json.JSONDecodeError:
        return None

    expires_at = (generated_at + timedelta(minutes=settings.profile_ai_insight_ttl_minutes)) if generated_at else None
    expired = expires_at is None or utc_now() >= expires_at
    return {
        'insight': insight if isinstance(insight, dict) else None,
        'fingerprint': fingerprint,
        'generated_at': generated_at,
        'expired': expired,
    }


def _parse_stored_timestamp(raw_value) -> datetime | None:
    normalized = str(raw_value or '').strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _store_cached_insight(
    db: Session,
    *,
    user_id: int,
    fingerprint: str,
    insight: dict,
) -> None:
    users = get_users_table(settings.users_table)
    now = utc_now()
    db.execute(
        users.update()
        .where(users.c.id == user_id)
        .values(
            profile_ai_insight_json=json.dumps(insight, ensure_ascii=False),
            profile_ai_insight_fingerprint=fingerprint,
            profile_ai_insight_generated_at=to_api_iso(now),
            updated_at=now,
        )
    )
    return now


def _serialize_insight_result(
    insight: dict | None,
    *,
    generated_at,
    cache_hit: bool,
) -> dict | None:
    if not isinstance(insight, dict):
        return None

    return {
        **insight,
        'generated_at': to_api_iso(generated_at),
        'ttl_minutes': settings.profile_ai_insight_ttl_minutes,
        'uses_ttl': True,
        'cache_hit': cache_hit,
    }

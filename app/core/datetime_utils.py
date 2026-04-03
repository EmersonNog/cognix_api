from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def to_api_iso(value: datetime | None) -> str | None:
    normalized = ensure_utc(value)
    if normalized is None:
        return None

    return normalized.isoformat()

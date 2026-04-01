from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_api_iso(value: datetime | None) -> str | None:
    if value is None:
        return None

    return value.isoformat()

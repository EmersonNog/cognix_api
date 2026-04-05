from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def app_timezone():
    try:
        return ZoneInfo(settings.app_timezone)
    except ZoneInfoNotFoundError:
        return timezone.utc


def local_now() -> datetime:
    return datetime.now(app_timezone())


def local_today() -> date:
    return local_now().date()


def local_day_bounds_in_utc(value: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(value, time.min, tzinfo=app_timezone())
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(
        timezone.utc
    )


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

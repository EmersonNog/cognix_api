from __future__ import annotations

from calendar import monthrange
from datetime import datetime

from app.core.datetime_utils import ensure_utc, utc_now

from ..shared.plans import PLAN_ID_ANUAL

def resolve_period_end(
    *,
    plan_id: str | None,
    explicit_period_end: datetime | None = None,
    period_started_at: datetime | None = None,
) -> datetime:
    normalized_period_end = ensure_utc(explicit_period_end)
    if normalized_period_end is not None:
        return normalized_period_end

    start = ensure_utc(period_started_at) or utc_now()
    if plan_id == PLAN_ID_ANUAL:
        return _add_years(start, 1)

    return _add_months(start, 1)

def parse_api_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return ensure_utc(value)

    if not isinstance(value, str):
        return None

    normalized = value.strip()
    if not normalized:
        return None

    try:
        return ensure_utc(datetime.fromisoformat(normalized.replace('Z', '+00:00')))
    except ValueError:
        return None

def _add_months(value: datetime, months: int) -> datetime:
    month_index = (value.month - 1) + months
    year = value.year + (month_index // 12)
    month = (month_index % 12) + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)

def _add_years(value: datetime, years: int) -> datetime:
    year = value.year + years
    day = min(value.day, monthrange(year, value.month)[1])
    return value.replace(year=year, day=day)

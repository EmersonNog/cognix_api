from __future__ import annotations

from datetime import timedelta

from app.core.config import settings

FULL_ACCESS_FEATURES = ('all',)
TRIAL_GRANT_TYPE = 'trial'

def trial_duration() -> timedelta:
    return timedelta(days=max(0, int(settings.cognix_trial_days)))

def full_access_features() -> list[str]:
    return list(FULL_ACCESS_FEATURES)

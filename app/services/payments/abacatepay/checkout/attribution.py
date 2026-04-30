from __future__ import annotations

import json
from collections.abc import Mapping

MAX_ATTRIBUTION_VALUE_LENGTH = 300
TRACKING_METADATA_PREFIX = 'tracking_'

ALLOWED_ATTRIBUTION_KEYS = frozenset(
    {
        'utm_source',
        'utm_medium',
        'utm_campaign',
        'utm_content',
        'utm_term',
        'src',
        'sck',
        'xcod',
        'fbclid',
        'gclid',
        'ttclid',
        '_fbp',
        '_fbc',
        'capturedAt',
        'landingPage',
        'referrer',
    }
)


def normalize_attribution(raw_attribution: object) -> dict[str, str]:
    if not isinstance(raw_attribution, Mapping):
        return {}

    attribution: dict[str, str] = {}
    for key, value in raw_attribution.items():
        if key not in ALLOWED_ATTRIBUTION_KEYS:
            continue

        sanitized = _sanitize_attribution_value(value)
        if sanitized:
            attribution[key] = sanitized

    return attribution


def attribution_to_json(attribution: dict[str, str]) -> str | None:
    normalized_attribution = normalize_attribution(attribution)
    if not normalized_attribution:
        return None

    return json.dumps(
        normalized_attribution,
        ensure_ascii=True,
        separators=(',', ':'),
        sort_keys=True,
    )


def attribution_from_json(value: object) -> dict[str, str]:
    if not isinstance(value, str) or not value.strip():
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}

    return normalize_attribution(parsed)


def attribution_metadata(attribution: dict[str, str]) -> dict[str, str]:
    normalized_attribution = normalize_attribution(attribution)
    return {
        f'{TRACKING_METADATA_PREFIX}{key}': value
        for key, value in normalized_attribution.items()
    }


def _sanitize_attribution_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    sanitized = ''.join(
        character
        for character in value.strip()
        if character >= ' ' and character != '\x7f'
    )

    return sanitized[:MAX_ATTRIBUTION_VALUE_LENGTH] or None

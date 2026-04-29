from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from app.core.config import settings
from app.core.datetime_utils import ensure_utc, utc_now


ACCESS_STATES = {
    'SUBSCRIPTION_STATE_ACTIVE',
    'SUBSCRIPTION_STATE_IN_GRACE_PERIOD',
}
CANCELLED_STATE = 'SUBSCRIPTION_STATE_CANCELED'
EXPIRED_STATES = {
    'SUBSCRIPTION_STATE_EXPIRED',
    'SUBSCRIPTION_STATE_PAUSED',
    'SUBSCRIPTION_STATE_ON_HOLD',
    'SUBSCRIPTION_STATE_PENDING',
}


@dataclass(frozen=True)
class GooglePlaySubscriptionSnapshot:
    product_id: str
    status: str
    subscription_state: str
    has_access: bool
    current_period_ends_at: datetime | None
    will_cancel_at_period_end: bool
    latest_order_id: str | None
    base_plan_id: str | None
    offer_id: str | None
    acknowledgement_state: str | None
    auto_renewing: bool | None


def google_play_product_ids() -> set[str]:
    return {
        settings.google_play_product_id_monthly,
        settings.google_play_product_id_annual,
    }


def snapshot_from_google_play_payload(
    payload: dict[str, Any],
    *,
    expected_product_id: str,
) -> GooglePlaySubscriptionSnapshot:
    line_item = _line_item_for_product(payload, expected_product_id)
    subscription_state = str(payload.get('subscriptionState') or '')
    expiry_time = _parse_expiry_time(line_item.get('expiryTime'))
    has_access = _has_access(subscription_state, expiry_time)
    status = _internal_status(subscription_state, has_access)
    offer_details = line_item.get('offerDetails')
    auto_renewing_plan = line_item.get('autoRenewingPlan')

    return GooglePlaySubscriptionSnapshot(
        product_id=expected_product_id,
        status=status,
        subscription_state=subscription_state,
        has_access=has_access,
        current_period_ends_at=expiry_time,
        will_cancel_at_period_end=status == 'cancelled' and has_access,
        latest_order_id=_optional_string(payload.get('latestOrderId')),
        base_plan_id=_offer_detail(offer_details, 'basePlanId'),
        offer_id=_offer_detail(offer_details, 'offerId'),
        acknowledgement_state=_optional_string(payload.get('acknowledgementState')),
        auto_renewing=_auto_renewing(auto_renewing_plan),
    )


def _line_item_for_product(
    payload: dict[str, Any],
    expected_product_id: str,
) -> dict[str, Any]:
    line_items = payload.get('lineItems')
    if not isinstance(line_items, list):
        raise HTTPException(
            status_code=502,
            detail='O Google Play não retornou os itens da assinatura.',
        )

    for item in line_items:
        if isinstance(item, dict) and item.get('productId') == expected_product_id:
            return item

    raise HTTPException(
        status_code=400,
        detail='A assinatura validada não corresponde ao plano solicitado.',
    )


def _has_access(
    subscription_state: str,
    expiry_time: datetime | None,
) -> bool:
    if subscription_state in ACCESS_STATES:
        return True

    if subscription_state == CANCELLED_STATE:
        return expiry_time is not None and expiry_time > utc_now()

    return False


def _internal_status(subscription_state: str, has_access: bool) -> str:
    if subscription_state in ACCESS_STATES:
        return 'active'

    if subscription_state == CANCELLED_STATE and has_access:
        return 'cancelled'

    if subscription_state in EXPIRED_STATES or subscription_state == CANCELLED_STATE:
        return 'expired'

    return 'pending'


def _parse_expiry_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return ensure_utc(datetime.fromisoformat(value.replace('Z', '+00:00')))
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail='O Google Play retornou uma data de expiração inválida.',
        ) from exc


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _offer_detail(value: object, key: str) -> str | None:
    if isinstance(value, dict):
        return _optional_string(value.get(key))
    return None


def _auto_renewing(value: object) -> bool | None:
    if not isinstance(value, dict):
        return None

    auto_renew_enabled = value.get('autoRenewEnabled')
    return auto_renew_enabled if isinstance(auto_renew_enabled, bool) else None

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.payments.abacatepay.subscriptions.persistence.records import (
    find_subscription_by_external_id,
    mark_subscription_utmify_result,
)

from .client import post_utmify_order
from .payloads import build_utmify_paid_order_payload


def sync_subscription_paid_order_with_utmify(
    db: Session,
    *,
    external_id: str,
    webhook_payload: dict,
) -> None:
    if not settings.utmify_api_token:
        return

    subscription = find_subscription_by_external_id(db, external_id)
    if not subscription or subscription.get('utmify_status') == 'sent':
        return

    order_payload = build_utmify_paid_order_payload(subscription, webhook_payload)

    try:
        post_utmify_order(order_payload)
    except Exception as exc:
        mark_subscription_utmify_result(
            db,
            external_id=external_id,
            status='failed',
            error=str(exc),
        )
        db.commit()
        return

    mark_subscription_utmify_result(
        db,
        external_id=external_id,
        status='sent',
    )
    db.commit()

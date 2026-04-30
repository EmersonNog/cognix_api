from __future__ import annotations

from sqlalchemy.orm import Session

from .context import build_webhook_context
from .events import SUPPORTED_EVENTS
from .subscriptions import (
    handle_subscription_cancelled,
    handle_subscription_completed,
)

def handle_abacatepay_webhook(db: Session, payload: dict) -> dict[str, str]:
    event = payload.get('event')

    if event not in SUPPORTED_EVENTS:
        return {'status': 'ignored'}

    context = build_webhook_context(payload)
    if context is None:
        return {'status': 'ignored'}

    if event == 'subscription.cancelled':
        return handle_subscription_cancelled(db, context)

    return handle_subscription_completed(db, context, payload)

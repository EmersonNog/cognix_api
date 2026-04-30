from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.payments.utmify import sync_subscription_paid_order_with_utmify

from ..coupons.redemptions import record_coupon_redeemed
from ..shared.external_ids import parse_coupon_context
from ..shared.plans import get_plan_config
from ..subscriptions.persistence.records import (
    mark_subscription_active,
    mark_subscription_cancelled_by_external_id,
)
from .context import WebhookContext

def handle_subscription_cancelled(
    db: Session,
    context: WebhookContext,
) -> dict[str, str]:
    mark_subscription_cancelled_by_external_id(
        db,
        external_id=context.external_id,
        external_subscription_id=context.external_subscription_id,
    )
    db.commit()
    return {'status': 'ok'}

def handle_subscription_completed(
    db: Session,
    context: WebhookContext,
    webhook_payload: dict | None = None,
) -> dict[str, str]:
    mark_subscription_active(
        db,
        external_id=context.external_id,
        external_subscription_id=context.external_subscription_id,
        checkout_id=context.checkout_id,
        checkout_url=context.checkout_url,
        current_period_ends_at=context.current_period_ends_at,
    )

    _record_coupon_redemption_if_present(db, context)
    db.commit()
    _sync_utmify_after_commit(db, context, webhook_payload)

    return {'status': 'ok'}


def _record_coupon_redemption_if_present(
    db: Session,
    context: WebhookContext,
) -> None:
    coupon_context = parse_coupon_context(context.external_id)
    if not coupon_context:
        return

    plan = get_plan_config(coupon_context['plan_id'])
    record_coupon_redeemed(
        db,
        coupon_code=coupon_context['coupon_code'],
        tax_id_hash=coupon_context['tax_id_hash'],
        email_hash=coupon_context['email_hash'],
        plan_id=coupon_context['plan_id'],
        product_id=plan.product_id,
        external_id=context.external_id,
        checkout_id=context.checkout_id,
        checkout_url=context.checkout_url,
    )


def _sync_utmify_after_commit(
    db: Session,
    context: WebhookContext,
    webhook_payload: dict | None,
) -> None:
    if webhook_payload is None:
        return

    sync_subscription_paid_order_with_utmify(
        db,
        external_id=context.external_id,
        webhook_payload=webhook_payload,
    )

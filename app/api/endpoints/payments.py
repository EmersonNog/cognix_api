import hmac
import json

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.services.payments.abacatepay.checkout.subscriptions import (
    create_subscription_checkout,
)
from app.services.payments.abacatepay.webhooks.handlers import (
    handle_abacatepay_webhook,
)

router = APIRouter()

class CreateAbacatePaySubscriptionPayload(BaseModel):
    planId: str
    name: str
    email: str
    taxId: str
    couponCode: str | None = None

@router.post('/abacatepay/subscription')
def create_abacatepay_subscription(
    payload: CreateAbacatePaySubscriptionPayload,
    db: Session = Depends(get_db),
) -> dict:
    checkout_url = create_subscription_checkout(
        db,
        plan_id=payload.planId,
        name=payload.name,
        email=payload.email,
        tax_id=payload.taxId,
        coupon_code=payload.couponCode,
    )

    return {'checkoutUrl': checkout_url}

@router.post('/abacatepay/webhook')
async def receive_abacatepay_webhook(
    request: Request,
    webhook_secret: str | None = Query(default=None, alias='webhookSecret'),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    raw_body = await request.body()

    _validate_webhook_secret(webhook_secret)

    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail='Payload de webhook inválido.') from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail='Payload de webhook inválido.')

    return handle_abacatepay_webhook(db, payload)


def _validate_webhook_secret(received_secret: str | None) -> None:
    expected_secret = settings.abacatepay_webhook_secret

    if expected_secret and not hmac.compare_digest(received_secret or '', expected_secret):
        raise HTTPException(status_code=401, detail='Webhook não autorizado.')

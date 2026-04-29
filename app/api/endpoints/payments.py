import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.endpoints.helpers import (
    current_user_email as _current_user_email,
    require_user_context,
)
from app.core.config import settings
from app.services.entitlements.status.current import get_current_access_status
from app.services.payments.abacatepay.checkout.subscriptions import (
    create_subscription_checkout,
)
from app.services.payments.abacatepay.subscriptions.current import (
    cancel_current_subscription,
    get_current_subscription_status,
)
from app.services.payments.abacatepay.webhooks.handlers import (
    handle_abacatepay_webhook,
)
from app.services.payments.google_play.subscriptions import (
    verify_google_play_subscription_purchase,
)

router = APIRouter()

class CreateAbacatePaySubscriptionPayload(BaseModel):
    planId: str
    name: str
    email: str
    taxId: str
    couponCode: str | None = None

class VerifyGooglePlaySubscriptionPayload(BaseModel):
    platform: str | None = None
    provider: str | None = None
    packageName: str
    productId: str
    purchaseId: str | None = None
    purchaseToken: str
    verificationSource: str | None = None
    localVerificationData: str | None = None
    transactionDate: str | None = None

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

@router.get('/abacatepay/subscription/current')
def get_abacatepay_current_subscription(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict:
    user_id, firebase_uid, email = _current_payment_user_context(user_claims)

    return get_current_subscription_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
    )

@router.post('/abacatepay/subscription/cancel')
def cancel_abacatepay_current_subscription(
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, firebase_uid, email = _current_payment_user_context(user_claims)

    return cancel_current_subscription(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
    )

@router.post('/google-play/subscription/verify')
def verify_google_play_subscription(
    payload: VerifyGooglePlaySubscriptionPayload,
    db: Session = Depends(get_db),
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, firebase_uid, email = _current_payment_user_context(user_claims)

    verify_google_play_subscription_purchase(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
        package_name=payload.packageName,
        product_id=payload.productId,
        purchase_token=payload.purchaseToken,
    )

    return get_current_access_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
    )

@router.post('/abacatepay/webhook')
async def receive_abacatepay_webhook(
    request: Request,
    webhook_secret: str | None = Query(default=None, alias='webhookSecret'),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    raw_body = await request.body()

    _validate_webhook_secret(webhook_secret)
    payload = _parse_webhook_payload(raw_body)

    return handle_abacatepay_webhook(db, payload)

def _current_payment_user_context(user_claims: dict) -> tuple[int, str, str | None]:
    user_id, firebase_uid = require_user_context(
        user_claims,
        require_firebase_uid=True,
    )

    return user_id, firebase_uid, _current_user_email(user_claims)

def _parse_webhook_payload(raw_body: bytes) -> dict:
    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail='Payload de webhook inválido.',
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail='Payload de webhook inválido.')

    return payload

def _validate_webhook_secret(received_secret: str | None) -> None:
    expected_secret = settings.abacatepay_webhook_secret

    if expected_secret and not hmac.compare_digest(
        received_secret or '',
        expected_secret,
    ):
        raise HTTPException(status_code=401, detail='Webhook não autorizado.')

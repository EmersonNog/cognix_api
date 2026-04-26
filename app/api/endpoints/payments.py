from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.payments import create_subscription_checkout

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
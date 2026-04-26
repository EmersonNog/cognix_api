from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException
from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import get_coupon_redemptions_table

from .checkout import CheckoutInput, normalize_coupon
from .plans import PLAN_ID_MENSAL, PlanConfig


def hash_identifier(value: str) -> str:
    secret = settings.abacatepay_hash_secret or settings.abacatepay_api_key

    if not secret:
        raise HTTPException(
            status_code=500,
            detail='Configure ABACATEPAY_HASH_SECRET no servidor.',
        )

    return hmac.new(
        secret.encode('utf-8'),
        value.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def should_apply_coupon(checkout: CheckoutInput, plan: PlanConfig) -> bool:
    configured_coupon = normalize_coupon(plan.coupon_code)
    apply_coupon = bool(checkout.coupon_code)

    if apply_coupon and checkout.coupon_code != configured_coupon:
        raise HTTPException(
            status_code=400,
            detail='Informe um cupom válido para o primeiro mês.',
        )

    if apply_coupon and checkout.plan_id != PLAN_ID_MENSAL:
        raise HTTPException(status_code=400, detail='Este cupom não se aplica ao plano escolhido.')

    return apply_coupon


def reserve_coupon(
    db: Session,
    *,
    coupon_code: str,
    tax_id_hash: str,
    email_hash: str,
    plan_id: str,
    product_id: str,
    external_id: str,
) -> None:
    redemptions = get_coupon_redemptions_table(settings.coupon_redemptions_table)

    try:
        db.execute(
            insert(redemptions).values(
                coupon_code=coupon_code,
                tax_id_hash=tax_id_hash,
                email_hash=email_hash,
                plan_id=plan_id,
                product_id=product_id,
                external_id=external_id,
                status='pending_checkout',
            )
        )
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail='Este cadastro ja utilizou o desconto de primeiro mes.',
        ) from exc


def mark_coupon_checkout_created(
    db: Session,
    *,
    external_id: str,
    checkout_id: str | None,
    checkout_url: str,
) -> None:
    redemptions = get_coupon_redemptions_table(settings.coupon_redemptions_table)
    db.execute(
        update(redemptions)
        .where(redemptions.c.external_id == external_id)
        .values(
            checkout_id=checkout_id,
            checkout_url=checkout_url,
            status='checkout_created',
        )
    )
    db.flush()

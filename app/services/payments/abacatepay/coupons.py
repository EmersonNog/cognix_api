from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException
from sqlalchemy import and_, insert, or_, select, update
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


def ensure_coupon_not_redeemed(
    db: Session,
    *,
    coupon_code: str,
    tax_id_hash: str,
    email_hash: str,
) -> None:
    redemptions = get_coupon_redemptions_table(settings.coupon_redemptions_table)
    existing_redemption = db.execute(
        select(redemptions.c.id).where(
            _same_coupon_customer(
                redemptions,
                coupon_code=coupon_code,
                tax_id_hash=tax_id_hash,
                email_hash=email_hash,
            ),
            redemptions.c.status == 'redeemed',
        )
    ).first()

    if existing_redemption:
        raise HTTPException(
            status_code=409,
            detail='Este CPF ou email ja utilizou o desconto de primeiro mes.',
        )


def record_coupon_redeemed(
    db: Session,
    *,
    coupon_code: str,
    tax_id_hash: str,
    email_hash: str,
    plan_id: str,
    product_id: str,
    external_id: str,
    checkout_id: str | None,
    checkout_url: str | None,
) -> None:
    redemptions = get_coupon_redemptions_table(settings.coupon_redemptions_table)
    values = {
        'coupon_code': coupon_code,
        'tax_id_hash': tax_id_hash,
        'email_hash': email_hash,
        'plan_id': plan_id,
        'product_id': product_id,
        'external_id': external_id,
        'checkout_id': checkout_id,
        'checkout_url': checkout_url,
        'status': 'redeemed',
    }

    existing_redemption = db.execute(
        select(redemptions.c.id).where(
            _same_coupon_customer(
                redemptions,
                coupon_code=coupon_code,
                tax_id_hash=tax_id_hash,
                email_hash=email_hash,
            )
        )
    ).first()

    if existing_redemption:
        db.execute(
            update(redemptions)
            .where(
                _same_coupon_customer(
                    redemptions,
                    coupon_code=coupon_code,
                    tax_id_hash=tax_id_hash,
                    email_hash=email_hash,
                )
            )
            .values(**values)
        )
        db.flush()
        return

    db.execute(insert(redemptions).values(**values))
    db.flush()


def _same_coupon_customer(
    redemptions,
    *,
    coupon_code: str,
    tax_id_hash: str,
    email_hash: str,
):
    return and_(
        redemptions.c.coupon_code == coupon_code,
        or_(
            redemptions.c.tax_id_hash == tax_id_hash,
            redemptions.c.email_hash == email_hash,
        ),
    )

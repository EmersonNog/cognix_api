from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import get_coupon_redemptions_table


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
            detail='Este CPF ou email já utilizou o desconto de primeiro mês.',
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

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from app.core.config import settings

PLAN_ID_MENSAL = 'mensal'
PLAN_ID_ANUAL = 'anual'
VALID_PLAN_IDS = {PLAN_ID_MENSAL, PLAN_ID_ANUAL}


@dataclass(frozen=True)
class PlanConfig:
    product_id: str
    coupon_code: str | None = None


def get_plan_config(plan_id: str) -> PlanConfig:
    if plan_id == PLAN_ID_MENSAL:
        product_id = settings.abacatepay_product_id_mensal
        coupon_code = settings.abacatepay_coupon_mensal_first_month
    elif plan_id == PLAN_ID_ANUAL:
        product_id = settings.abacatepay_product_id_anual
        coupon_code = None
    else:
        raise HTTPException(status_code=400, detail='Plano inválido.')

    if not product_id:
        raise HTTPException(
            status_code=500,
            detail=f'Configure o produto AbacatePay do plano {plan_id}.',
        )

    return PlanConfig(product_id=product_id, coupon_code=coupon_code)

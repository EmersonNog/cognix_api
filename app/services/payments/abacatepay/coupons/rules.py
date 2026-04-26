from __future__ import annotations

from fastapi import HTTPException

from ..checkout.inputs import CheckoutInput, normalize_coupon
from ..shared.plans import PLAN_ID_MENSAL, PlanConfig


def should_apply_coupon(checkout: CheckoutInput, plan: PlanConfig) -> bool:
    configured_coupon = normalize_coupon(plan.coupon_code)
    apply_coupon = bool(checkout.coupon_code)

    if apply_coupon and checkout.coupon_code != configured_coupon:
        raise HTTPException(
            status_code=400,
            detail='Informe um cupom válido para o primeiro mês.',
        )

    if apply_coupon and checkout.plan_id != PLAN_ID_MENSAL:
        raise HTTPException(
            status_code=400,
            detail='Este cupom não se aplica ao plano escolhido.',
        )

    return apply_coupon

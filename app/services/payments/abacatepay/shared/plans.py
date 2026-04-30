from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException

from app.core.config import settings

PLAN_ID_MENSAL = 'mensal'
PLAN_ID_ANUAL = 'anual'

SettingsValue = Callable[[], str | None]


@dataclass(frozen=True)
class PlanConfig:
    product_id: str
    name: str = ''
    price_cents: int = 0
    coupon_code: str | None = None
    coupon_price_cents: int | None = None


@dataclass(frozen=True)
class PlanDefinition:
    name: str
    price_cents: int
    product_id: SettingsValue
    coupon_code: SettingsValue = lambda: None
    coupon_price_cents: int | None = None


_PLAN_DEFINITIONS = {
    PLAN_ID_MENSAL: PlanDefinition(
        name='Plano mensal',
        price_cents=1990,
        product_id=lambda: settings.abacatepay_product_id_mensal,
        coupon_code=lambda: settings.abacatepay_coupon_mensal_first_month,
        coupon_price_cents=990,
    ),
    PLAN_ID_ANUAL: PlanDefinition(
        name='Plano anual',
        price_cents=19990,
        product_id=lambda: settings.abacatepay_product_id_anual,
    ),
}

VALID_PLAN_IDS = set(_PLAN_DEFINITIONS)


def get_plan_config(plan_id: str) -> PlanConfig:
    plan_definition = _PLAN_DEFINITIONS.get(plan_id)
    if plan_definition is None:
        raise HTTPException(status_code=400, detail='Plano inválido.')

    product_id = plan_definition.product_id()
    if not product_id:
        raise HTTPException(
            status_code=500,
            detail=f'Configure o produto AbacatePay do plano {plan_id}.',
        )

    return PlanConfig(
        product_id=product_id,
        name=plan_definition.name,
        price_cents=plan_definition.price_cents,
        coupon_code=plan_definition.coupon_code(),
        coupon_price_cents=plan_definition.coupon_price_cents,
    )


def resolve_checkout_price_cents(
    plan: PlanConfig,
    *,
    coupon_applied: bool,
) -> int:
    if coupon_applied and plan.coupon_price_cents is not None:
        return plan.coupon_price_cents

    return plan.price_cents

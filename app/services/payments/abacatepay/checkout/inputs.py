from __future__ import annotations

import re
from dataclasses import dataclass, field

from fastapi import HTTPException

from ..shared.plans import VALID_PLAN_IDS
from .attribution import normalize_attribution

@dataclass(frozen=True)
class CheckoutInput:
    plan_id: str
    name: str
    email: str
    tax_id: str
    coupon_code: str
    attribution: dict[str, str] = field(default_factory=dict)

def normalize_coupon(value: str | None) -> str:
    return re.sub(r'[^A-Z0-9_-]', '', (value or '').upper())[:30]

def normalize_checkout_input(
    *,
    plan_id: str,
    name: str,
    email: str,
    tax_id: str,
    coupon_code: str | None,
    attribution: object | None = None,
) -> CheckoutInput:
    return CheckoutInput(
        plan_id=plan_id.strip(),
        name=name.strip(),
        email=email.strip().lower(),
        tax_id=re.sub(r'\D+', '', tax_id),
        coupon_code=normalize_coupon(coupon_code),
        attribution=normalize_attribution(attribution),
    )


def validate_checkout_input(checkout: CheckoutInput) -> None:
    if checkout.plan_id not in VALID_PLAN_IDS:
        raise HTTPException(status_code=400, detail='Plano inválido.')

    if len(checkout.name) < 2 or len(checkout.name) > 120:
        raise HTTPException(status_code=400, detail='Informe um nome válido.')

    if '@' not in checkout.email or len(checkout.email) > 320:
        raise HTTPException(status_code=400, detail='Informe um email válido.')

    if not _is_valid_cpf(checkout.tax_id):
        raise HTTPException(status_code=400, detail='Informe um CPF válido.')


def _is_valid_cpf(cpf: str) -> bool:
    if not re.fullmatch(r'\d{11}', cpf):
        return False

    if len(set(cpf)) == 1:
        return False

    for position in (9, 10):
        total = sum(int(cpf[digit]) * ((position + 1) - digit) for digit in range(position))
        expected_digit = ((total * 10) % 11) % 10

        if int(cpf[position]) != expected_digit:
            return False

    return True

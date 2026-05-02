import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException

from app.core.config import settings
from app.services.payments.abacatepay.shared.external_ids import (
    new_external_id,
    parse_coupon_context,
    parse_plan_id,
)
from app.services.payments.abacatepay.shared.plans import (
    PlanConfig,
    get_plan_config,
    resolve_checkout_price_cents,
)


class AbacatePayExternalIdTests(unittest.TestCase):
    def test_new_external_id_without_coupon_uses_expected_format(self) -> None:
        frozen_now = datetime(2026, 4, 27, 12, 34, 56, tzinfo=timezone.utc)

        with (
            patch(
                'app.services.payments.abacatepay.shared.external_ids.datetime',
            ) as datetime_mock,
            patch(
                'app.services.payments.abacatepay.shared.external_ids.secrets.token_hex',
                return_value='abc12345',
            ),
        ):
            datetime_mock.now.return_value = frozen_now
            external_id = new_external_id('mensal')

        self.assertEqual(external_id, 'cognix.mensal.20260427123456.abc12345')
        datetime_mock.now.assert_called_once_with(timezone.utc)

    def test_new_external_id_with_coupon_uses_expected_format(self) -> None:
        frozen_now = datetime(2026, 4, 27, 12, 34, 56, tzinfo=timezone.utc)

        with (
            patch(
                'app.services.payments.abacatepay.shared.external_ids.datetime',
            ) as datetime_mock,
            patch(
                'app.services.payments.abacatepay.shared.external_ids.secrets.token_hex',
                return_value='abc12345',
            ),
        ):
            datetime_mock.now.return_value = frozen_now
            external_id = new_external_id(
                'mensal',
                coupon_code='COGNIX10',
                tax_id_hash='taxhash',
                email_hash='emailhash',
            )

        self.assertEqual(
            external_id,
            'cognix.mensal.20260427123456.COGNIX10.taxhash.emailhash.abc12345',
        )

    def test_parse_coupon_context_returns_coupon_data(self) -> None:
        coupon_context = parse_coupon_context(
            'cognix.mensal.20260427123456.COGNIX10.taxhash.emailhash.abc12345'
        )

        self.assertEqual(
            coupon_context,
            {
                'plan_id': 'mensal',
                'coupon_code': 'COGNIX10',
                'tax_id_hash': 'taxhash',
                'email_hash': 'emailhash',
            },
        )

    def test_parse_coupon_context_rejects_non_coupon_external_id(self) -> None:
        self.assertIsNone(parse_coupon_context('cognix.mensal.20260427123456.abc12345'))
        self.assertIsNone(
            parse_coupon_context(
                'cognix.mensal.20260427123456..taxhash.emailhash.abc12345'
            )
        )

    def test_parse_plan_id_supports_checkout_and_coupon_formats(self) -> None:
        self.assertEqual(
            parse_plan_id('cognix.mensal.20260427123456.abc12345'),
            'mensal',
        )
        self.assertEqual(
            parse_plan_id(
                'cognix.anual.20260427123456.COGNIX10.taxhash.emailhash.abc12345'
            ),
            'anual',
        )

    def test_parse_plan_id_rejects_invalid_formats(self) -> None:
        self.assertIsNone(parse_plan_id('mensal.20260427123456.abc12345'))
        self.assertIsNone(parse_plan_id('cognix..20260427123456.abc12345'))
        self.assertIsNone(parse_plan_id('cognix.mensal.abc12345'))


class AbacatePayPlansTests(unittest.TestCase):
    def test_get_plan_config_returns_monthly_plan(self) -> None:
        with (
            patch.object(settings, 'abacatepay_product_id_mensal', 'prod_mensal'),
            patch.object(settings, 'abacatepay_coupon_mensal_first_month', 'COGNIX10'),
        ):
            plan = get_plan_config('mensal')

        self.assertEqual(plan.product_id, 'prod_mensal')
        self.assertEqual(plan.name, 'Plano mensal')
        self.assertEqual(plan.price_cents, 2990)
        self.assertEqual(plan.coupon_code, 'COGNIX10')
        self.assertEqual(plan.coupon_price_cents, 1990)

    def test_get_plan_config_returns_annual_plan(self) -> None:
        with patch.object(settings, 'abacatepay_product_id_anual', 'prod_anual'):
            plan = get_plan_config('anual')

        self.assertEqual(plan.product_id, 'prod_anual')
        self.assertEqual(plan.name, 'Plano anual')
        self.assertEqual(plan.price_cents, 29900)
        self.assertIsNone(plan.coupon_code)
        self.assertIsNone(plan.coupon_price_cents)

    def test_resolve_checkout_price_cents_uses_coupon_price_when_available(self) -> None:
        plan = PlanConfig(
            product_id='prod_mensal',
            price_cents=2990,
            coupon_price_cents=1990,
        )

        self.assertEqual(
            resolve_checkout_price_cents(plan, coupon_applied=True),
            1990,
        )
        self.assertEqual(
            resolve_checkout_price_cents(plan, coupon_applied=False),
            2990,
        )

    def test_get_plan_config_rejects_invalid_plan(self) -> None:
        with self.assertRaises(HTTPException) as exc_info:
            get_plan_config('vitalicio')

        self.assertEqual(exc_info.exception.status_code, 400)
        self.assertEqual(exc_info.exception.detail, 'Plano inválido.')

    def test_get_plan_config_requires_configured_product(self) -> None:
        with patch.object(settings, 'abacatepay_product_id_mensal', None):
            with self.assertRaises(HTTPException) as exc_info:
                get_plan_config('mensal')

        self.assertEqual(exc_info.exception.status_code, 500)
        self.assertEqual(
            exc_info.exception.detail,
            'Configure o produto AbacatePay do plano mensal.',
        )


if __name__ == '__main__':
    unittest.main()

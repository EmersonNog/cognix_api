import hashlib
import hmac
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models.tables.payments import get_coupon_redemptions_table
from app.services.payments.abacatepay.checkout.inputs import CheckoutInput
from app.services.payments.abacatepay.coupons.identifiers import hash_identifier
from app.services.payments.abacatepay.coupons.redemptions import (
    ensure_coupon_not_redeemed,
    record_coupon_redeemed,
)
from app.services.payments.abacatepay.coupons.rules import should_apply_coupon
from app.services.payments.abacatepay.shared.plans import PlanConfig


class CouponIdentifierTests(unittest.TestCase):
    def test_hash_identifier_uses_hash_secret_when_configured(self) -> None:
        with (
            patch.object(settings, 'abacatepay_hash_secret', 'hash-secret'),
            patch.object(settings, 'abacatepay_api_key', 'api-key'),
        ):
            hashed = hash_identifier('aluno@example.com')

        self.assertEqual(
            hashed,
            hmac.new(
                b'hash-secret',
                b'aluno@example.com',
                hashlib.sha256,
            ).hexdigest(),
        )

    def test_hash_identifier_falls_back_to_api_key(self) -> None:
        with (
            patch.object(settings, 'abacatepay_hash_secret', None),
            patch.object(settings, 'abacatepay_api_key', 'api-key'),
        ):
            hashed = hash_identifier('52998224725')

        self.assertEqual(
            hashed,
            hmac.new(
                b'api-key',
                b'52998224725',
                hashlib.sha256,
            ).hexdigest(),
        )

    def test_hash_identifier_requires_secret_or_api_key(self) -> None:
        with (
            patch.object(settings, 'abacatepay_hash_secret', None),
            patch.object(settings, 'abacatepay_api_key', None),
        ):
            with self.assertRaises(HTTPException) as exc_info:
                hash_identifier('aluno@example.com')

        self.assertEqual(exc_info.exception.status_code, 500)
        self.assertEqual(
            exc_info.exception.detail,
            'Configure ABACATEPAY_HASH_SECRET no servidor.',
        )


class CouponRuleTests(unittest.TestCase):
    def test_should_apply_coupon_accepts_valid_monthly_coupon(self) -> None:
        checkout = CheckoutInput(
            plan_id='mensal',
            name='Aluno Teste',
            email='aluno@example.com',
            tax_id='52998224725',
            coupon_code='COGNIX10',
        )

        self.assertTrue(
            should_apply_coupon(
                checkout,
                PlanConfig(product_id='prod_mensal', coupon_code='COGNIX10'),
            )
        )

    def test_should_apply_coupon_returns_false_for_blank_coupon(self) -> None:
        checkout = CheckoutInput(
            plan_id='mensal',
            name='Aluno Teste',
            email='aluno@example.com',
            tax_id='52998224725',
            coupon_code='',
        )

        self.assertFalse(
            should_apply_coupon(
                checkout,
                PlanConfig(product_id='prod_mensal', coupon_code='COGNIX10'),
            )
        )

    def test_should_apply_coupon_rejects_invalid_coupon(self) -> None:
        checkout = CheckoutInput(
            plan_id='mensal',
            name='Aluno Teste',
            email='aluno@example.com',
            tax_id='52998224725',
            coupon_code='INVALIDO',
        )

        with self.assertRaises(HTTPException) as exc_info:
            should_apply_coupon(
                checkout,
                PlanConfig(product_id='prod_mensal', coupon_code='COGNIX10'),
            )

        self.assertEqual(exc_info.exception.status_code, 400)

    def test_should_apply_coupon_rejects_coupon_for_non_monthly_plan(self) -> None:
        checkout = CheckoutInput(
            plan_id='anual',
            name='Aluno Teste',
            email='aluno@example.com',
            tax_id='52998224725',
            coupon_code='COGNIX10',
        )

        with self.assertRaises(HTTPException) as exc_info:
            should_apply_coupon(
                checkout,
                PlanConfig(product_id='prod_anual', coupon_code='COGNIX10'),
            )

        self.assertEqual(exc_info.exception.status_code, 400)


class CouponRedemptionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine('sqlite:///:memory:')
        self.table_name = f'test_coupon_redemptions_{self._testMethodName}'
        self.table = get_coupon_redemptions_table(self.table_name)
        self.table.create(self.engine, checkfirst=True)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.settings_patcher = patch.object(
            settings,
            'coupon_redemptions_table',
            self.table_name,
        )
        self.settings_patcher.start()

    def tearDown(self) -> None:
        self.settings_patcher.stop()
        self.db.close()
        self.engine.dispose()

    def test_ensure_coupon_not_redeemed_allows_pending_checkout(self) -> None:
        self.db.execute(
            insert(self.table).values(
                coupon_code='COGNIX10',
                tax_id_hash='tax-hash',
                email_hash='email-hash',
                plan_id='mensal',
                product_id='prod_mensal',
                external_id='external-1',
                checkout_id='bill_1',
                checkout_url='https://app.abacatepay.com/pay/bill_1',
                status='pending_checkout',
            )
        )
        self.db.commit()

        ensure_coupon_not_redeemed(
            self.db,
            coupon_code='COGNIX10',
            tax_id_hash='tax-hash',
            email_hash='email-hash',
        )

    def test_ensure_coupon_not_redeemed_blocks_redeemed_coupon(self) -> None:
        self.db.execute(
            insert(self.table).values(
                coupon_code='COGNIX10',
                tax_id_hash='other-tax-hash',
                email_hash='email-hash',
                plan_id='mensal',
                product_id='prod_mensal',
                external_id='external-1',
                checkout_id='bill_1',
                checkout_url='https://app.abacatepay.com/pay/bill_1',
                status='redeemed',
            )
        )
        self.db.commit()

        with self.assertRaises(HTTPException) as exc_info:
            ensure_coupon_not_redeemed(
                self.db,
                coupon_code='COGNIX10',
                tax_id_hash='tax-hash',
                email_hash='email-hash',
            )

        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertIn('desconto', exc_info.exception.detail)

    def test_record_coupon_redeemed_inserts_new_redemption(self) -> None:
        record_coupon_redeemed(
            self.db,
            coupon_code='COGNIX10',
            tax_id_hash='tax-hash',
            email_hash='email-hash',
            plan_id='mensal',
            product_id='prod_mensal',
            external_id='external-1',
            checkout_id='bill_1',
            checkout_url='https://app.abacatepay.com/pay/bill_1',
        )

        row = self.db.execute(select(self.table)).mappings().one()

        self.assertEqual(row['coupon_code'], 'COGNIX10')
        self.assertEqual(row['tax_id_hash'], 'tax-hash')
        self.assertEqual(row['email_hash'], 'email-hash')
        self.assertEqual(row['status'], 'redeemed')
        self.assertEqual(row['checkout_id'], 'bill_1')

    def test_record_coupon_redeemed_updates_existing_redemption(self) -> None:
        self.db.execute(
            insert(self.table).values(
                coupon_code='COGNIX10',
                tax_id_hash='tax-hash',
                email_hash='email-hash',
                plan_id='mensal',
                product_id='prod_mensal',
                external_id='external-1',
                checkout_id='bill_old',
                checkout_url='https://app.abacatepay.com/pay/bill_old',
                status='pending_checkout',
            )
        )
        self.db.commit()

        record_coupon_redeemed(
            self.db,
            coupon_code='COGNIX10',
            tax_id_hash='tax-hash',
            email_hash='email-hash',
            plan_id='mensal',
            product_id='prod_mensal_v2',
            external_id='external-2',
            checkout_id='bill_new',
            checkout_url='https://app.abacatepay.com/pay/bill_new',
        )

        rows = self.db.execute(select(self.table)).mappings().all()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'redeemed')
        self.assertEqual(rows[0]['product_id'], 'prod_mensal_v2')
        self.assertEqual(rows[0]['external_id'], 'external-2')
        self.assertEqual(rows[0]['checkout_id'], 'bill_new')


if __name__ == '__main__':
    unittest.main()

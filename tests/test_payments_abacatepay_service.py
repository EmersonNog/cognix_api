import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.core.config import settings
from app.services.payments.abacatepay.checkout.inputs import CheckoutInput
from app.services.payments.abacatepay.checkout.subscriptions import (
    create_subscription_checkout,
)
from app.services.payments.abacatepay.gateway.payloads import subscription_payload
from app.services.payments.abacatepay.shared.plans import PlanConfig
from app.services.payments.abacatepay.subscriptions.current import (
    cancel_current_subscription,
    get_current_subscription_status,
)
from app.services.payments.abacatepay.webhooks.handlers import (
    handle_abacatepay_webhook,
)


class AbacatePaySubscriptionCheckoutTests(unittest.TestCase):
    def test_coupon_checkout_creation_checks_only_redeemed_usage(self) -> None:
        db = Mock()
        db.execute.return_value.first.return_value = None

        with (
            patch.object(settings, 'abacatepay_product_id_mensal', 'prod_mensal'),
            patch.object(settings, 'abacatepay_coupon_mensal_first_month', 'COGNIX10'),
            patch.object(settings, 'abacatepay_hash_secret', 'test-secret'),
            patch(
                'app.services.payments.abacatepay.checkout.subscriptions.create_customer',
                return_value='cust_123',
            ),
            patch(
                'app.services.payments.abacatepay.checkout.subscriptions.create_subscription',
                return_value=('https://app.abacatepay.com/pay/bill_123', 'bill_123'),
            ) as create_subscription_mock,
        ):
            checkout_url = create_subscription_checkout(
                db,
                plan_id='mensal',
                name='Aluno Teste',
                email='aluno@example.com',
                tax_id='529.982.247-25',
                coupon_code='COGNIX10',
            )

        self.assertEqual(checkout_url, 'https://app.abacatepay.com/pay/bill_123')
        db.commit.assert_called_once()
        self.assertEqual(db.execute.call_count, 2)
        create_subscription_mock.assert_called_once()
        self.assertEqual(
            create_subscription_mock.call_args.kwargs['allowed_coupon_code'],
            'COGNIX10',
        )

    def test_pending_checkout_does_not_block_same_cpf_coupon_attempt(self) -> None:
        db = Mock()
        db.execute.return_value.first.return_value = None

        with (
            patch.object(settings, 'abacatepay_product_id_mensal', 'prod_mensal'),
            patch.object(settings, 'abacatepay_coupon_mensal_first_month', 'COGNIX10'),
            patch.object(settings, 'abacatepay_hash_secret', 'test-secret'),
            patch(
                'app.services.payments.abacatepay.checkout.subscriptions.create_customer',
                return_value='cust_123',
            ),
            patch(
                'app.services.payments.abacatepay.checkout.subscriptions.create_subscription',
                return_value=('https://app.abacatepay.com/pay/bill_123', 'bill_123'),
            ) as create_subscription_mock,
        ):
            first_url = create_subscription_checkout(
                db,
                plan_id='mensal',
                name='Aluno Teste',
                email='aluno@example.com',
                tax_id='529.982.247-25',
                coupon_code='COGNIX10',
            )
            second_url = create_subscription_checkout(
                db,
                plan_id='mensal',
                name='Aluno Teste',
                email='aluno@example.com',
                tax_id='529.982.247-25',
                coupon_code='COGNIX10',
            )

        self.assertEqual(first_url, 'https://app.abacatepay.com/pay/bill_123')
        self.assertEqual(second_url, 'https://app.abacatepay.com/pay/bill_123')
        self.assertEqual(db.execute.call_count, 4)
        self.assertEqual(db.commit.call_count, 2)
        self.assertEqual(create_subscription_mock.call_count, 2)

    def test_redeemed_coupon_blocks_same_cpf_checkout(self) -> None:
        db = Mock()
        db.execute.return_value.first.return_value = object()

        with (
            patch.object(settings, 'abacatepay_product_id_mensal', 'prod_mensal'),
            patch.object(settings, 'abacatepay_coupon_mensal_first_month', 'COGNIX10'),
            patch.object(settings, 'abacatepay_hash_secret', 'test-secret'),
            patch(
                'app.services.payments.abacatepay.checkout.subscriptions.create_customer',
            ) as create_customer_mock,
            patch(
                'app.services.payments.abacatepay.checkout.subscriptions.create_subscription',
            ) as create_subscription_mock,
        ):
            with self.assertRaises(HTTPException) as exc_info:
                create_subscription_checkout(
                    db,
                    plan_id='mensal',
                    name='Aluno Teste',
                    email='aluno@example.com',
                    tax_id='529.982.247-25',
                    coupon_code='COGNIX10',
                )

        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertEqual(
            exc_info.exception.detail,
            'Este CPF ou email já utilizou o desconto de primeiro mês.',
        )
        create_customer_mock.assert_not_called()
        create_subscription_mock.assert_not_called()
        db.commit.assert_not_called()

    def test_blank_coupon_does_not_allow_coupon(self) -> None:
        db = Mock()

        with (
            patch.object(settings, 'abacatepay_product_id_mensal', 'prod_mensal'),
            patch.object(settings, 'abacatepay_coupon_mensal_first_month', 'COGNIX10'),
            patch.object(settings, 'abacatepay_hash_secret', 'test-secret'),
            patch(
                'app.services.payments.abacatepay.checkout.subscriptions.create_customer',
                return_value='cust_123',
            ),
            patch(
                'app.services.payments.abacatepay.checkout.subscriptions.create_subscription',
                return_value=('https://app.abacatepay.com/pay/bill_123', 'bill_123'),
            ) as create_subscription_mock,
        ):
            checkout_url = create_subscription_checkout(
                db,
                plan_id='mensal',
                name='Aluno Teste',
                email='aluno@example.com',
                tax_id='529.982.247-25',
                coupon_code=None,
            )

        self.assertEqual(checkout_url, 'https://app.abacatepay.com/pay/bill_123')
        db.commit.assert_called_once()
        db.execute.assert_called_once()
        create_subscription_mock.assert_called_once()
        self.assertIsNone(
            create_subscription_mock.call_args.kwargs['allowed_coupon_code'],
        )

    def test_abacatepay_payload_includes_allowed_coupon(self) -> None:
        checkout = CheckoutInput(
            plan_id='mensal',
            name='Aluno Teste',
            email='aluno@example.com',
            tax_id='52998224725',
            coupon_code='',
        )

        payload = subscription_payload(
            checkout=checkout,
            plan=PlanConfig(product_id='prod_mensal', coupon_code='COGNIX10'),
            customer_id='cust_123',
            external_id='cognix-mensal-123',
            tax_id_hash='tax-hash',
            allowed_coupon_code='COGNIX10',
        )

        self.assertEqual(payload['coupons'], ['COGNIX10'])
        self.assertEqual(
            payload['metadata']['firstMonthDiscountCoupon'],
            'COGNIX10',
        )

    def test_invalid_coupon_is_rejected_before_checkout_creation(self) -> None:
        db = Mock()

        with (
            patch.object(settings, 'abacatepay_product_id_mensal', 'prod_mensal'),
            patch.object(settings, 'abacatepay_coupon_mensal_first_month', 'COGNIX10'),
            patch.object(settings, 'abacatepay_hash_secret', 'test-secret'),
            patch(
                'app.services.payments.abacatepay.checkout.subscriptions.create_customer',
            ) as create_customer_mock,
            patch(
                'app.services.payments.abacatepay.checkout.subscriptions.create_subscription',
            ) as create_subscription_mock,
        ):
            with self.assertRaises(HTTPException) as exc_info:
                create_subscription_checkout(
                    db,
                    plan_id='mensal',
                    name='Aluno Teste',
                    email='aluno@example.com',
                    tax_id='529.982.247-25',
                    coupon_code='INVALIDO',
                )

        self.assertEqual(exc_info.exception.status_code, 400)
        self.assertEqual(
            exc_info.exception.detail,
            'Informe um cupom válido para o primeiro mês.',
        )
        create_customer_mock.assert_not_called()
        create_subscription_mock.assert_not_called()
        db.execute.assert_not_called()
        db.commit.assert_not_called()

    def test_webhook_marks_coupon_redemption_as_redeemed(self) -> None:
        db = Mock()
        db.execute.return_value.first.return_value = None
        payload = {
            'event': 'subscription.completed',
            'data': {
                'checkout': {
                    'id': 'bill_123',
                    'externalId': (
                        'cognix.mensal.20260426120000.COGNIX10.'
                        'taxhash.emailhash.abc123'
                    ),
                    'url': 'https://app.abacatepay.com/pay/bill_123',
                    'status': 'PAID',
                },
            },
        }

        result = handle_abacatepay_webhook(db, payload)

        self.assertEqual(result, {'status': 'ok'})
        self.assertEqual(db.execute.call_count, 3)
        db.commit.assert_called_once()

    def test_cancel_current_subscription_calls_abacatepay_and_marks_cancelled(self) -> None:
        db = Mock()
        period_end = datetime(2099, 5, 26, tzinfo=timezone.utc)
        db.execute.return_value.mappings.return_value.first.return_value = {
            'id': 10,
            'user_id': 7,
            'firebase_uid': 'firebase-7',
            'email_hash': 'emailhash',
            'plan_id': 'mensal',
            'status': 'active',
            'external_subscription_id': 'subs_123',
            'current_period_ends_at': period_end,
        }

        with (
            patch.object(settings, 'abacatepay_hash_secret', 'test-secret'),
            patch(
                'app.services.payments.abacatepay.subscriptions.current.cancel_subscription',
            ) as cancel_subscription_mock,
        ):
            result = cancel_current_subscription(
                db,
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
            )

        self.assertEqual(
            result,
            {
                'status': 'cancelled',
                'hasAccess': True,
                'accessEndsAt': '2099-05-26T00:00:00+00:00',
            },
        )
        cancel_subscription_mock.assert_called_once_with('subs_123')
        db.commit.assert_called_once()

    def test_current_subscription_status_keeps_cancelled_access_until_period_end(self) -> None:
        db = Mock()
        db.execute.return_value.mappings.return_value.first.return_value = {
            'id': 10,
            'user_id': 7,
            'firebase_uid': 'firebase-7',
            'email_hash': 'emailhash',
            'plan_id': 'mensal',
            'status': 'cancelled',
            'external_subscription_id': 'subs_123',
            'current_period_ends_at': datetime(2099, 5, 26, tzinfo=timezone.utc),
        }

        with patch.object(settings, 'abacatepay_hash_secret', 'test-secret'):
            result = get_current_subscription_status(
                db,
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
            )

        self.assertEqual(result['status'], 'cancelled')
        self.assertTrue(result['hasAccess'])
        self.assertFalse(result['canCancel'])
        self.assertTrue(result['willCancelAtPeriodEnd'])
        self.assertEqual(result['accessEndsAt'], '2099-05-26T00:00:00+00:00')

    def test_cancel_current_subscription_rejects_missing_active_subscription(self) -> None:
        db = Mock()
        db.execute.return_value.mappings.return_value.first.return_value = None

        with patch.object(settings, 'abacatepay_hash_secret', 'test-secret'):
            with self.assertRaises(HTTPException) as exc_info:
                cancel_current_subscription(
                    db,
                    user_id=7,
                    firebase_uid='firebase-7',
                    email='aluno@example.com',
                )

        self.assertEqual(exc_info.exception.status_code, 404)
        db.commit.assert_not_called()


if __name__ == '__main__':
    unittest.main()

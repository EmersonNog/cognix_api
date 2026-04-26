import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.core.config import settings
from app.services.payments.abacatepay.checkout.inputs import CheckoutInput
from app.services.payments.abacatepay.checkout.subscriptions import (
    create_subscription_checkout,
)
from app.services.payments.abacatepay.gateway.payloads import subscription_payload
from app.services.payments.abacatepay.shared.plans import PlanConfig
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
        db.execute.assert_called_once()
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
        self.assertEqual(db.execute.call_count, 2)
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
            'Este CPF ou email ja utilizou o desconto de primeiro mes.',
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
        db.execute.assert_not_called()
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
        self.assertEqual(db.execute.call_count, 2)
        db.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()

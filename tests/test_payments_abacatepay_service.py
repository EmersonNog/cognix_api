import unittest
from unittest.mock import Mock, patch

from app.core.config import settings
from app.services.payments.abacatepay.service import create_subscription_checkout


class AbacatePaySubscriptionCheckoutTests(unittest.TestCase):
    def test_coupon_checkout_creation_does_not_reserve_or_attach_coupon(self) -> None:
        db = Mock()

        with (
            patch.object(settings, 'abacatepay_product_id_mensal', 'prod_mensal'),
            patch.object(settings, 'abacatepay_coupon_mensal_first_month', 'COGNIX10'),
            patch.object(settings, 'abacatepay_hash_secret', 'test-secret'),
            patch(
                'app.services.payments.abacatepay.service.create_customer',
                return_value='cust_123',
            ),
            patch(
                'app.services.payments.abacatepay.service.create_subscription',
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
        self.assertEqual(db.commit.call_count, 2)
        db.execute.assert_not_called()
        self.assertTrue(
            all(
                not call.kwargs['apply_coupon']
                for call in create_subscription_mock.call_args_list
            )
        )


if __name__ == '__main__':
    unittest.main()

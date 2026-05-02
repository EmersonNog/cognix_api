import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.core.config import settings
from app.services.entitlements.status.current import (
    get_current_access_status,
    get_current_subscription_status,
)
from app.services.payments.google_play.subscriptions.current import (
    get_current_google_play_subscription_status,
)
from app.services.payments.google_play.subscriptions.records import (
    upsert_google_play_subscription,
)
from app.services.payments.google_play.subscriptions.status import (
    GooglePlaySubscriptionSnapshot,
    snapshot_from_google_play_payload,
)
from app.services.payments.google_play.subscriptions.verification import (
    verify_google_play_subscription_purchase,
)


class GooglePlaySubscriptionStatusTests(unittest.TestCase):
    def test_snapshot_uses_active_google_play_subscription(self) -> None:
        expiry = '2099-05-26T12:00:00Z'
        payload = {
            'subscriptionState': 'SUBSCRIPTION_STATE_ACTIVE',
            'acknowledgementState': 'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED',
            'latestOrderId': 'GPA.1234-5678-9012-34567',
            'lineItems': [
                {
                    'productId': 'cognix_premium_monthly',
                    'expiryTime': expiry,
                    'offerDetails': {
                        'basePlanId': 'monthly',
                        'offerId': 'app-first-month-990',
                    },
                    'autoRenewingPlan': {'autoRenewEnabled': True},
                },
            ],
        }

        snapshot = snapshot_from_google_play_payload(
            payload,
            expected_product_id='cognix_premium_monthly',
        )

        self.assertEqual(snapshot.status, 'active')
        self.assertTrue(snapshot.has_access)
        self.assertEqual(snapshot.base_plan_id, 'monthly')
        self.assertEqual(snapshot.offer_id, 'app-first-month-990')
        self.assertTrue(snapshot.auto_renewing)
        self.assertEqual(
            snapshot.current_period_ends_at,
            datetime(2099, 5, 26, 12, 0, tzinfo=timezone.utc),
        )

    def test_snapshot_rejects_mismatched_product(self) -> None:
        payload = {
            'subscriptionState': 'SUBSCRIPTION_STATE_ACTIVE',
            'lineItems': [{'productId': 'outro_produto'}],
        }

        with self.assertRaises(HTTPException) as exc_info:
            snapshot_from_google_play_payload(
                payload,
                expected_product_id='cognix_premium_monthly',
            )

        self.assertEqual(exc_info.exception.status_code, 400)


class GooglePlayVerificationTests(unittest.TestCase):
    def test_verification_fetches_google_and_persists_snapshot(self) -> None:
        db = Mock()
        payload = {
            'subscriptionState': 'SUBSCRIPTION_STATE_ACTIVE',
            'latestOrderId': 'GPA.1234-5678-9012-34567',
            'lineItems': [
                {
                    'productId': 'cognix_premium_annual',
                    'expiryTime': '2099-05-26T12:00:00Z',
                    'offerDetails': {'basePlanId': 'annual'},
                    'autoRenewingPlan': {'autoRenewEnabled': True},
                },
            ],
        }

        with (
            patch.object(settings, 'google_play_package_name', 'com.cognixhub.app'),
            patch.object(
                settings,
                'google_play_product_id_annual',
                'cognix_premium_annual',
            ),
            patch.object(settings, 'abacatepay_hash_secret', 'test-secret'),
            patch(
                'app.services.payments.google_play.subscriptions.verification.'
                'fetch_google_play_subscription_purchase',
                return_value=payload,
            ) as fetch_mock,
            patch(
                'app.services.payments.google_play.subscriptions.verification.'
                'acknowledge_google_play_subscription_purchase',
            ) as acknowledge_mock,
            patch(
                'app.services.payments.google_play.subscriptions.verification.'
                'upsert_google_play_subscription',
            ) as upsert_mock,
        ):
            verify_google_play_subscription_purchase(
                db,
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
                package_name='com.cognixhub.app',
                product_id='cognix_premium_annual',
                purchase_token='purchase-token-123',
            )

        fetch_mock.assert_called_once_with(
            package_name='com.cognixhub.app',
            purchase_token='purchase-token-123',
        )
        acknowledge_mock.assert_called_once_with(
            package_name='com.cognixhub.app',
            product_id='cognix_premium_annual',
            purchase_token='purchase-token-123',
        )
        upsert_mock.assert_called_once()
        self.assertEqual(upsert_mock.call_args.kwargs['user_id'], 7)
        self.assertEqual(
            upsert_mock.call_args.kwargs['snapshot'].product_id,
            'cognix_premium_annual',
        )
        self.assertEqual(
            upsert_mock.call_args.kwargs['snapshot'].acknowledgement_state,
            'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED',
        )
        db.commit.assert_called_once()


    def test_subscription_token_cannot_be_linked_to_another_account(self) -> None:
        db = Mock()
        snapshot = GooglePlaySubscriptionSnapshot(
            product_id='cognix_premium_monthly',
            status='active',
            subscription_state='SUBSCRIPTION_STATE_ACTIVE',
            has_access=True,
            current_period_ends_at=datetime(2099, 5, 26, 12, 0, tzinfo=timezone.utc),
            will_cancel_at_period_end=False,
            latest_order_id='GPA.1234-5678-9012-34567',
            base_plan_id='monthly',
            offer_id='app-first-month-990',
            acknowledgement_state='ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED',
            auto_renewing=True,
        )

        with (
            patch.object(
                settings,
                'google_play_subscriptions_table',
                'google_play_subscriptions',
            ),
            patch(
                'app.services.payments.google_play.subscriptions.records.'
                '_find_subscription_by_token',
                return_value={'user_id': 99},
            ),
            self.assertRaises(HTTPException) as exc_info,
        ):
            upsert_google_play_subscription(
                db,
                user_id=7,
                firebase_uid='firebase-7',
                email_hash='email-hash',
                package_name='com.cognixhub.app',
                purchase_token='purchase-token-123',
                snapshot=snapshot,
                raw_payload={},
            )

        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertEqual(
            exc_info.exception.detail['code'],
            'subscription_linked_to_another_account',
        )


class GooglePlayEntitlementTests(unittest.TestCase):
    def test_current_google_play_status_refreshes_cancellation(self) -> None:
        period_end = datetime.now(timezone.utc) + timedelta(days=30)
        stale_subscription = {
            'user_id': 7,
            'firebase_uid': 'firebase-7',
            'email_hash': 'hash-1',
            'package_name': 'com.cognixhub.app',
            'product_id': 'cognix_premium_annual',
            'purchase_token': 'purchase-token-123',
            'status': 'active',
            'current_period_ends_at': period_end,
        }
        refreshed_subscription = {
            **stale_subscription,
            'status': 'cancelled',
        }

        with (
            patch(
                'app.services.payments.google_play.subscriptions.current.'
                'find_current_google_play_subscription_for_user',
                side_effect=[stale_subscription, refreshed_subscription],
            ),
            patch(
                'app.services.payments.google_play.subscriptions.current.'
                'verify_google_play_subscription_purchase',
            ) as verify_mock,
        ):
            result = get_current_google_play_subscription_status(
                Mock(),
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
            )

        verify_mock.assert_called_once_with(
            unittest.mock.ANY,
            user_id=7,
            firebase_uid='firebase-7',
            email='aluno@example.com',
            package_name='com.cognixhub.app',
            product_id='cognix_premium_annual',
            purchase_token='purchase-token-123',
        )
        self.assertEqual(result['status'], 'cancelled')
        self.assertTrue(result['hasAccess'])
        self.assertTrue(result['willCancelAtPeriodEnd'])
        self.assertFalse(result['canCancel'])

    def test_current_subscription_prefers_active_google_play_subscription(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(days=30)
        google_subscription = {
            'status': 'active',
            'provider': 'google_play',
            'planId': 'cognix_premium_monthly',
            'hasAccess': True,
            'accessEndsAt': future.isoformat(),
            'willCancelAtPeriodEnd': False,
            'canCancel': True,
        }

        with (
            patch(
                'app.services.entitlements.status.current.'
                'get_current_google_play_subscription_status',
                return_value=google_subscription,
            ),
            patch(
                'app.services.entitlements.status.current.'
                'get_abacatepay_subscription_status',
                return_value={
                    'status': 'none',
                    'canCancel': False,
                    'hasAccess': False,
                    'accessEndsAt': None,
                    'willCancelAtPeriodEnd': False,
                },
            ),
        ):
            result = get_current_subscription_status(
                Mock(),
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
            )

        self.assertEqual(result, google_subscription)

    def test_entitlement_response_includes_google_play_provider(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(days=30)
        db = Mock()

        with (
            patch(
                'app.services.entitlements.status.current.'
                'get_current_subscription_status',
                return_value={
                    'status': 'active',
                    'provider': 'google_play',
                    'planId': 'cognix_premium_monthly',
                    'hasAccess': True,
                    'accessEndsAt': future.isoformat(),
                    'willCancelAtPeriodEnd': False,
                    'canCancel': True,
                },
            ),
            patch(
                'app.services.entitlements.status.current.find_user_grant',
                return_value=None,
            ),
        ):
            result = get_current_access_status(
                db,
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
            )

        self.assertEqual(result['accessStatus'], 'subscription')
        self.assertEqual(result['activeSource'], 'google_play')
        self.assertEqual(result['subscriptionProvider'], 'google_play')
        self.assertTrue(result['hasFullAccess'])


if __name__ == '__main__':
    unittest.main()

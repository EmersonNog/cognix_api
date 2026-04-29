import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from app.services.entitlements.status.current import get_current_access_status
from app.services.entitlements.trials.service import start_trial


class EntitlementsStatusTests(unittest.TestCase):
    def test_current_access_status_allows_trial_start_when_no_access_exists(self) -> None:
        db = Mock()

        with (
            patch(
                'app.services.entitlements.status.current.get_current_subscription_status',
                return_value={
                    'status': 'none',
                    'canCancel': False,
                    'hasAccess': False,
                    'accessEndsAt': None,
                    'willCancelAtPeriodEnd': False,
                },
            ),
            patch(
                'app.services.entitlements.status.current.find_user_grant',
                return_value=None,
            ),
            patch(
                'app.services.entitlements.status.current.'
                'has_used_monthly_intro_offer',
                return_value=False,
            ),
        ):
            result = get_current_access_status(
                db,
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
            )

        self.assertEqual(result['accessStatus'], 'trial_available')
        self.assertFalse(result['hasFullAccess'])
        self.assertTrue(result['trialAvailable'])
        self.assertTrue(result['eligibleForMonthlyIntroOffer'])
        self.assertEqual(result['features'], [])

    def test_current_access_status_blocks_monthly_intro_when_offer_was_used(self) -> None:
        db = Mock()

        with (
            patch(
                'app.services.entitlements.status.current.get_current_subscription_status',
                return_value={
                    'status': 'none',
                    'canCancel': False,
                    'hasAccess': False,
                    'accessEndsAt': None,
                    'willCancelAtPeriodEnd': False,
                },
            ),
            patch(
                'app.services.entitlements.status.current.find_user_grant',
                return_value=None,
            ),
            patch(
                'app.services.entitlements.status.current.'
                'has_used_monthly_intro_offer',
                return_value=True,
            ),
        ):
            result = get_current_access_status(
                db,
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
            )

        self.assertFalse(result['eligibleForMonthlyIntroOffer'])

    def test_current_access_status_uses_active_trial(self) -> None:
        db = Mock()
        now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
        starts_at = now - timedelta(hours=1)
        ends_at = now + timedelta(days=2)

        with (
            patch(
                'app.services.entitlements.status.current.get_current_subscription_status',
                return_value={
                    'status': 'none',
                    'canCancel': False,
                    'hasAccess': False,
                    'accessEndsAt': None,
                    'willCancelAtPeriodEnd': False,
                },
            ),
            patch('app.services.entitlements.status.current.utc_now', return_value=now),
            patch(
                'app.services.entitlements.status.current.find_user_grant',
                return_value={
                    'id': 12,
                    'status': 'active',
                    'starts_at': starts_at,
                    'ends_at': ends_at,
                },
            ),
            patch(
                'app.services.entitlements.status.current.'
                'has_used_monthly_intro_offer',
                return_value=False,
            ),
        ):
            result = get_current_access_status(
                db,
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
            )

        self.assertEqual(result['accessStatus'], 'trial')
        self.assertTrue(result['hasFullAccess'])
        self.assertFalse(result['trialAvailable'])
        self.assertEqual(result['activeSource'], 'trial')
        self.assertEqual(result['features'], ['all'])

    def test_current_access_status_expires_elapsed_trial(self) -> None:
        db = Mock()
        now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)

        with (
            patch(
                'app.services.entitlements.status.current.get_current_subscription_status',
                return_value={
                    'status': 'none',
                    'canCancel': False,
                    'hasAccess': False,
                    'accessEndsAt': None,
                    'willCancelAtPeriodEnd': False,
                },
            ),
            patch('app.services.entitlements.status.current.utc_now', return_value=now),
            patch(
                'app.services.entitlements.status.current.find_user_grant',
                return_value={
                    'id': 12,
                    'status': 'active',
                    'starts_at': now - timedelta(days=4),
                    'ends_at': now - timedelta(days=1),
                },
            ),
            patch(
                'app.services.entitlements.status.current.mark_user_grant_expired',
            ) as mark_expired_mock,
            patch(
                'app.services.entitlements.status.current.'
                'has_used_monthly_intro_offer',
                return_value=False,
            ),
        ):
            result = get_current_access_status(
                db,
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
            )

        self.assertEqual(result['accessStatus'], 'trial_expired')
        self.assertFalse(result['hasFullAccess'])
        self.assertFalse(result['trialAvailable'])
        mark_expired_mock.assert_called_once_with(db, grant_id=12)
        db.commit.assert_called_once()


class EntitlementsTrialTests(unittest.TestCase):
    def test_start_trial_creates_trial_and_returns_updated_access(self) -> None:
        db = Mock()
        active_result = {
            'accessStatus': 'trial',
            'hasFullAccess': True,
            'activeSource': 'trial',
            'trialAvailable': False,
        }

        with (
            patch(
                'app.services.entitlements.trials.service.get_current_access_status',
                side_effect=[
                    {
                        'accessStatus': 'trial_available',
                        'hasFullAccess': False,
                        'trialAvailable': True,
                    },
                    active_result,
                ],
            ),
            patch(
                'app.services.entitlements.trials.service.create_user_grant',
            ) as create_grant_mock,
            patch(
                'app.services.entitlements.trials.service.trial_duration',
                return_value=timedelta(days=3),
            ),
        ):
            result = start_trial(
                db,
                user_id=7,
                firebase_uid='firebase-7',
                email='aluno@example.com',
            )

        self.assertEqual(result, active_result)
        create_grant_mock.assert_called_once()
        self.assertEqual(create_grant_mock.call_args.kwargs['user_id'], 7)
        self.assertEqual(
            create_grant_mock.call_args.kwargs['firebase_uid'],
            'firebase-7',
        )
        self.assertEqual(
            create_grant_mock.call_args.kwargs['grant_type'],
            'trial',
        )
        db.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()

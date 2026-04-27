import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.api.deps.entitlements import (
    PREMIUM_ACCESS_DENIED_DETAIL,
    ensure_full_access_for_claims,
)


class EntitlementsAccessGuardTests(unittest.TestCase):
    def test_full_access_guard_allows_active_access(self) -> None:
        db = Mock()
        claims = {
            'uid': 'firebase-7',
            'email': 'aluno@example.com',
            'internal_user': {'id': 7},
        }
        access_status = {'hasFullAccess': True, 'accessStatus': 'trial'}

        with patch(
            'app.api.deps.entitlements.get_current_access_status',
            return_value=access_status,
        ) as get_status_mock:
            result = ensure_full_access_for_claims(db, claims)

        self.assertEqual(result, access_status)
        get_status_mock.assert_called_once_with(
            db,
            user_id=7,
            firebase_uid='firebase-7',
            email='aluno@example.com',
        )

    def test_full_access_guard_blocks_missing_access(self) -> None:
        db = Mock()
        claims = {
            'uid': 'firebase-7',
            'email': 'aluno@example.com',
            'internal_user': {'id': 7},
        }

        with (
            patch(
                'app.api.deps.entitlements.get_current_access_status',
                return_value={'hasFullAccess': False, 'accessStatus': 'trial_expired'},
            ),
            self.assertRaises(HTTPException) as exc_info,
        ):
            ensure_full_access_for_claims(db, claims)

        self.assertEqual(exc_info.exception.status_code, 403)
        self.assertEqual(exc_info.exception.detail, PREMIUM_ACCESS_DENIED_DETAIL)


if __name__ == '__main__':
    unittest.main()

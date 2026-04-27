import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.api.endpoints.helpers import (
    current_user_email,
    normalize_required_text,
    require_recent_authentication,
    require_user_context,
)


class ApiEndpointHelpersTests(unittest.TestCase):
    def test_require_user_context_returns_user_id_and_firebase_uid(self) -> None:
        user_id, firebase_uid = require_user_context(
            {
                'uid': 'firebase-7',
                'internal_user': {'id': '7'},
            },
            require_firebase_uid=True,
        )

        self.assertEqual(user_id, 7)
        self.assertEqual(firebase_uid, 'firebase-7')

    def test_require_user_context_rejects_missing_firebase_uid_when_required(self) -> None:
        with self.assertRaises(HTTPException) as exc_info:
            require_user_context(
                {
                    'internal_user': {'id': 7},
                },
                require_firebase_uid=True,
            )

        self.assertEqual(exc_info.exception.status_code, 401)
        self.assertEqual(exc_info.exception.detail, 'Unauthorized')

    @patch('app.api.endpoints.helpers.utc_now')
    def test_require_recent_authentication_accepts_recent_login(self, utc_now_mock) -> None:
        utc_now_mock.return_value.timestamp.return_value = 1_000

        require_recent_authentication({'auth_time': 800}, max_age_seconds=300)

    @patch('app.api.endpoints.helpers.utc_now')
    def test_require_recent_authentication_rejects_stale_login(self, utc_now_mock) -> None:
        utc_now_mock.return_value.timestamp.return_value = 1_000

        with self.assertRaises(HTTPException) as exc_info:
            require_recent_authentication({'auth_time': 600}, max_age_seconds=300)

        self.assertEqual(exc_info.exception.status_code, 403)
        self.assertEqual(
            exc_info.exception.detail,
            'Recent authentication required',
        )

    def test_current_user_email_prefers_claim_email(self) -> None:
        self.assertEqual(
            current_user_email(
                {
                    'email': 'claim@example.com',
                    'internal_user': {'email': 'internal@example.com'},
                }
            ),
            'claim@example.com',
        )

    def test_current_user_email_falls_back_to_internal_user_email(self) -> None:
        self.assertEqual(
            current_user_email({'internal_user': {'email': 'internal@example.com'}}),
            'internal@example.com',
        )

    def test_normalize_required_text_trims_values(self) -> None:
        self.assertEqual(
            normalize_required_text('avatar_seed', '  avatar-123  '),
            'avatar-123',
        )

    def test_normalize_required_text_rejects_empty_values(self) -> None:
        with self.assertRaises(HTTPException) as exc_info:
            normalize_required_text('avatar_seed', '   ')

        self.assertEqual(exc_info.exception.status_code, 400)
        self.assertEqual(exc_info.exception.detail, 'avatar_seed is required')


if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.api.endpoints.attempts import upsert_attempt
from app.services.economy import (
    DEFAULT_AVATAR_SEED,
    coins_from_half_units,
    select_profile_avatar,
)
from app.services.economy.catalog import build_avatar_store_payload


class EconomyTests(unittest.TestCase):
    def test_coins_from_half_units_supports_half_steps(self) -> None:
        self.assertEqual(coins_from_half_units(0), 0.0)
        self.assertEqual(coins_from_half_units(1), 0.5)
        self.assertEqual(coins_from_half_units(7), 3.5)

    def test_avatar_store_marks_owned_equipped_and_affordable_flags(self) -> None:
        items = build_avatar_store_payload(
            coins_half_units=12,
            equipped_avatar_seed='avatar_3',
            owned_avatar_seeds=[DEFAULT_AVATAR_SEED, 'avatar_3'],
        )

        avatar_1 = next(item for item in items if item['seed'] == DEFAULT_AVATAR_SEED)
        avatar_3 = next(item for item in items if item['seed'] == 'avatar_3')
        avatar_6 = next(item for item in items if item['seed'] == 'avatar_6')

        self.assertTrue(avatar_1['owned'])
        self.assertFalse(avatar_1['equipped'])
        self.assertTrue(avatar_3['owned'])
        self.assertTrue(avatar_3['equipped'])
        self.assertTrue(avatar_3['affordable'])
        self.assertFalse(avatar_6['owned'])
        self.assertFalse(avatar_6['affordable'])

    @patch('app.api.endpoints.attempts._fetch_question_lookup')
    def test_attempt_rejects_unknown_question_before_awarding(self, lookup_mock) -> None:
        lookup_mock.return_value = (False, None)
        db = MagicMock()

        with self.assertRaises(HTTPException) as ctx:
            upsert_attempt(
                {
                    'question_id': 999999,
                    'selected_letter': 'A',
                },
                db=db,
                user_claims={'internal_user': {'id': 1}, 'uid': 'user-1'},
            )

        self.assertEqual(ctx.exception.status_code, 404)
        db.commit.assert_not_called()

    @patch('app.services.economy.avatars.ensure_user_economy_defaults')
    @patch('app.services.economy.avatars.lock_user_economy_row')
    @patch('app.services.economy.avatars.fetch_user_economy_state')
    def test_avatar_purchase_returns_insufficient_funds_when_atomic_debit_fails(
        self,
        state_mock,
        lock_mock,
        ensure_defaults_mock,
    ) -> None:
        ensure_defaults_mock.return_value = None
        lock_mock.return_value = {
            'id': 1,
            'coins_half_units': 4,
            'equipped_avatar_seed': DEFAULT_AVATAR_SEED,
        }
        state_mock.side_effect = [
            {
                'coins_half_units': 12,
                'coins_balance': 6.0,
                'equipped_avatar_seed': DEFAULT_AVATAR_SEED,
                'owned_avatar_seeds': [DEFAULT_AVATAR_SEED],
                'avatar_store': [],
            },
            {
                'coins_half_units': 4,
                'coins_balance': 2.0,
                'equipped_avatar_seed': DEFAULT_AVATAR_SEED,
                'owned_avatar_seeds': [DEFAULT_AVATAR_SEED],
                'avatar_store': [],
            },
        ]
        db = MagicMock()
        db.execute.return_value.first.return_value = None

        result = select_profile_avatar(
            db,
            user_id=1,
            firebase_uid='user-1',
            avatar_seed='avatar_3',
        )

        self.assertEqual(result['status'], 'insufficient_funds')
        self.assertEqual(result['action'], 'insufficient_funds')
        self.assertEqual(result['required_coins'], 5.0)
        self.assertEqual(result['missing_coins'], 3.0)


if __name__ == '__main__':
    unittest.main()

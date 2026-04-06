import unittest
from unittest.mock import Mock, patch

from app.services.account.service import delete_user_account


class _FakeColumn:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other):
        return (self.name, '==', other)


class _FakeColumns:
    def __init__(self, *names: str) -> None:
        for name in names:
            setattr(self, name, _FakeColumn(name))


class _FakeTable:
    def __init__(self, *column_names: str) -> None:
        self.c = _FakeColumns(*column_names)


class _DeleteStatement:
    def __init__(self, table) -> None:
        self.table = table
        self.conditions = []

    def where(self, condition):
        self.conditions.append(condition)
        return self


class DeleteUserAccountTests(unittest.TestCase):
    @patch('app.services.account.service.get_firebase_app', return_value=object())
    @patch('app.services.account.service.auth.delete_user')
    @patch('app.services.account.service.get_users_table')
    @patch('app.services.account.service.get_user_study_plan_table')
    @patch('app.services.account.service.get_user_avatar_inventory_table')
    @patch('app.services.account.service.get_user_coin_ledger_table')
    @patch('app.services.account.service.get_user_summaries_table')
    @patch('app.services.account.service.get_session_history_table')
    @patch('app.services.account.service.get_sessions_table')
    @patch('app.services.account.service.get_attempt_history_table')
    @patch('app.services.account.service.get_attempts_table')
    @patch('app.services.account.service.delete')
    def test_delete_user_account_removes_internal_rows_and_firebase_user(
        self,
        delete_mock,
        get_attempts_table_mock,
        get_attempt_history_table_mock,
        get_sessions_table_mock,
        get_session_history_table_mock,
        get_user_summaries_table_mock,
        get_user_coin_ledger_table_mock,
        get_user_avatar_inventory_table_mock,
        get_user_study_plan_table_mock,
        get_users_table_mock,
        delete_user_mock,
        _get_firebase_app_mock,
    ) -> None:
        attempts = _FakeTable('user_id')
        attempt_history = _FakeTable('user_id')
        sessions = _FakeTable('user_id')
        session_history = _FakeTable('user_id')
        user_summaries = _FakeTable('user_id')
        user_coin_ledger = _FakeTable('user_id')
        user_avatar_inventory = _FakeTable('user_id')
        user_study_plan = _FakeTable('user_id')
        users = _FakeTable('id', 'firebase_uid')

        get_attempts_table_mock.return_value = attempts
        get_attempt_history_table_mock.return_value = attempt_history
        get_sessions_table_mock.return_value = sessions
        get_session_history_table_mock.return_value = session_history
        get_user_summaries_table_mock.return_value = user_summaries
        get_user_coin_ledger_table_mock.return_value = user_coin_ledger
        get_user_avatar_inventory_table_mock.return_value = user_avatar_inventory
        get_user_study_plan_table_mock.return_value = user_study_plan
        get_users_table_mock.return_value = users
        delete_mock.side_effect = lambda table: _DeleteStatement(table)

        db = Mock()

        result = delete_user_account(db, user_id=7, firebase_uid='uid-7')

        self.assertEqual(result, {'status': 'ok'})
        self.assertEqual(db.execute.call_count, 9)
        delete_user_mock.assert_called_once()
        db.commit.assert_called_once()
        db.rollback.assert_not_called()

    @patch('app.services.account.service.get_firebase_app', return_value=object())
    @patch('app.services.account.service.auth.delete_user', side_effect=RuntimeError('boom'))
    @patch('app.services.account.service.get_users_table', return_value=_FakeTable('id', 'firebase_uid'))
    @patch('app.services.account.service.get_user_study_plan_table', return_value=_FakeTable('user_id'))
    @patch('app.services.account.service.get_user_avatar_inventory_table', return_value=_FakeTable('user_id'))
    @patch('app.services.account.service.get_user_coin_ledger_table', return_value=_FakeTable('user_id'))
    @patch('app.services.account.service.get_user_summaries_table', return_value=_FakeTable('user_id'))
    @patch('app.services.account.service.get_session_history_table', return_value=_FakeTable('user_id'))
    @patch('app.services.account.service.get_sessions_table', return_value=_FakeTable('user_id'))
    @patch('app.services.account.service.get_attempt_history_table', return_value=_FakeTable('user_id'))
    @patch('app.services.account.service.get_attempts_table', return_value=_FakeTable('user_id'))
    @patch('app.services.account.service.delete', side_effect=lambda table: _DeleteStatement(table))
    def test_delete_user_account_rolls_back_when_firebase_delete_fails(
        self,
        _delete_mock,
        _get_attempts_table_mock,
        _get_attempt_history_table_mock,
        _get_sessions_table_mock,
        _get_session_history_table_mock,
        _get_user_summaries_table_mock,
        _get_user_coin_ledger_table_mock,
        _get_user_avatar_inventory_table_mock,
        _get_user_study_plan_table_mock,
        _get_users_table_mock,
        _delete_user_mock,
        _get_firebase_app_mock,
    ) -> None:
        db = Mock()

        with self.assertRaises(RuntimeError):
            delete_user_account(db, user_id=7, firebase_uid='uid-7')

        db.commit.assert_not_called()
        db.rollback.assert_called_once()


if __name__ == '__main__':
    unittest.main()

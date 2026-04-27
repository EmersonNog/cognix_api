import unittest
from unittest.mock import patch

from app.db.models.schema.entitlements import ensure_user_access_grants_schema


class _RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement) -> None:
        self.statements.append(str(statement))


class _BeginContext:
    def __init__(self, connection: _RecordingConnection) -> None:
        self.connection = connection

    def __enter__(self) -> _RecordingConnection:
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False


class _RecordingEngine:
    def __init__(self) -> None:
        self.connection = _RecordingConnection()

    def begin(self) -> _BeginContext:
        return _BeginContext(self.connection)


def _quote(_engine, identifier: str) -> str:
    return f'"{identifier}"'


class EntitlementsSchemaTests(unittest.TestCase):
    def test_ensure_user_access_grants_schema_ignores_missing_table(self) -> None:
        engine = _RecordingEngine()

        with patch(
            'app.db.models.schema.entitlements.table_exists',
            return_value=False,
        ):
            ensure_user_access_grants_schema(engine, 'user_access_grants')

        self.assertEqual(engine.connection.statements, [])

    def test_ensure_user_access_grants_schema_hardens_existing_table(self) -> None:
        engine = _RecordingEngine()

        with (
            patch(
                'app.db.models.schema.entitlements.table_exists',
                return_value=True,
            ),
            patch(
                'app.db.models.schema.entitlements.get_column_names',
                return_value={'id', 'user_id'},
            ),
            patch(
                'app.db.models.schema.entitlements.quote_identifier',
                side_effect=_quote,
            ),
        ):
            ensure_user_access_grants_schema(engine, 'user_access_grants')

        statements = engine.connection.statements
        joined_statements = '\n'.join(statements)

        self.assertIn(
            'ALTER TABLE "user_access_grants" '
            'ADD COLUMN IF NOT EXISTS grant_type VARCHAR(64)',
            joined_statements,
        )
        self.assertIn(
            'PARTITION BY user_id, grant_type',
            joined_statements,
        )
        self.assertIn(
            'CREATE UNIQUE INDEX IF NOT EXISTS '
            '"uq_user_access_grants_user_grant_type"',
            joined_statements,
        )
        self.assertIn(
            'WHERE user_id IS NOT NULL AND grant_type IS NOT NULL',
            joined_statements,
        )


if __name__ == '__main__':
    unittest.main()
